"""Service d'impression tickets ESC/POS via réseau TCP.

Formate et envoie les tickets vers une imprimante thermique 80mm
connectée en réseau (port 9100 raw TCP).

Types de tickets :
    - vente_epicerie : ticket de caisse POS épicerie
    - commande_cuisine : bon de commande pour la cuisine restaurant
    - recu_restaurant : reçu client restaurant

Format ESC/POS :
    - En-tête : logo bitmap + nom commerce + adresse + SIRET + tél
    - Corps : lignes article (désignation, qté, PU, total)
    - TVA : ventilation par taux (5.5%, 10%, 20%)
    - Total TTC en gras
    - Pied : mention légale + date/heure + n° ticket + opérateur
    - QR code : URL vers reçu numérique
    - Commande tiroir-caisse (épicerie)
"""
import logging
import socket
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ── ESC/POS Commands ──────────────────────────────────────────────────────────

ESC = b'\x1b'
GS = b'\x1d'

CMD_INIT = ESC + b'@'                    # Initialize printer
CMD_CUT = GS + b'V' + b'\x41' + b'\x03' # Partial cut
CMD_BOLD_ON = ESC + b'E' + b'\x01'
CMD_BOLD_OFF = ESC + b'E' + b'\x00'
CMD_ALIGN_CENTER = ESC + b'a' + b'\x01'
CMD_ALIGN_LEFT = ESC + b'a' + b'\x00'
CMD_ALIGN_RIGHT = ESC + b'a' + b'\x02'
CMD_DOUBLE_HEIGHT = ESC + b'!' + b'\x10'
CMD_NORMAL_SIZE = ESC + b'!' + b'\x00'
CMD_CODEPAGE_858 = ESC + b't' + b'\x13'  # CP858 (accents français)
CMD_FEED_LINES = ESC + b'd'               # + 1 byte (n lines)
CMD_KICK_DRAWER = ESC + b'p' + b'\x00' + b'\x19' + b'\xfa'  # Pin 2, 25ms on, 250ms off

PAPER_WIDTH_CHARS = 48  # 80mm = 48 chars en font A

# ── Data structures ───────────────────────────────────────────────────────────


@dataclass
class TicketLine:
    designation: str
    quantite: int = 1
    prix_unitaire_cts: int = 0
    total_cts: int = 0


@dataclass
class TvaBreakdown:
    taux_label: str          # "20%", "10%", "5.5%"
    base_ht_cts: int = 0
    montant_tva_cts: int = 0


@dataclass
class TicketData:
    """Données pour formater un ticket."""
    # En-tête commerce
    nom_commerce: str = ""
    adresse: str = ""
    siret: str = ""
    telephone: str = ""

    # Contenu
    lignes: list[TicketLine] = field(default_factory=list)
    sous_total_ht_cts: int = 0
    tva_breakdown: list[TvaBreakdown] = field(default_factory=list)
    total_ttc_cts: int = 0

    # Pied
    numero_ticket: str = ""
    operateur: str = ""
    mention_legale: str = "Merci de votre visite"
    qr_url: Optional[str] = None

    # Options
    ouvrir_tiroir: bool = False
    ticket_type: str = "vente_epicerie"


# ── Formatting helpers ────────────────────────────────────────────────────────


def _fmt_cts(cts: int) -> str:
    """Formate des centimes en euros : 1250 → '12,50'."""
    euros = cts / 100
    return f"{euros:,.2f}".replace(",", " ").replace(".", ",")


def _line_two_cols(left: str, right: str, width: int = PAPER_WIDTH_CHARS) -> str:
    """Formate une ligne avec texte aligné gauche et droite."""
    space = width - len(left) - len(right)
    if space < 1:
        left = left[:width - len(right) - 1]
        space = 1
    return left + " " * space + right


def _separator(char: str = "-", width: int = PAPER_WIDTH_CHARS) -> str:
    return char * width


# ── Ticket builder ────────────────────────────────────────────────────────────


def build_ticket_bytes(data: TicketData) -> bytes:
    """Construit les bytes ESC/POS pour un ticket complet."""
    buf = bytearray()
    buf += CMD_INIT
    buf += CMD_CODEPAGE_858

    # ── En-tête ───────────────────────────────────────────────
    buf += CMD_ALIGN_CENTER

    if data.nom_commerce:
        buf += CMD_BOLD_ON + CMD_DOUBLE_HEIGHT
        buf += data.nom_commerce.encode("cp858", errors="replace") + b'\n'
        buf += CMD_NORMAL_SIZE + CMD_BOLD_OFF

    if data.adresse:
        buf += data.adresse.encode("cp858", errors="replace") + b'\n'
    if data.siret:
        buf += f"SIRET: {data.siret}".encode("cp858", errors="replace") + b'\n'
    if data.telephone:
        buf += f"Tél: {data.telephone}".encode("cp858", errors="replace") + b'\n'

    buf += CMD_ALIGN_LEFT
    buf += _separator("=").encode("cp858") + b'\n'

    # ── Date + opérateur ──────────────────────────────────────
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    buf += _line_two_cols(now, data.operateur or "").encode("cp858") + b'\n'
    if data.numero_ticket:
        buf += f"Ticket: {data.numero_ticket}".encode("cp858") + b'\n'
    buf += _separator("-").encode("cp858") + b'\n'

    # ── Lignes article ────────────────────────────────────────
    for ligne in data.lignes:
        desig = ligne.designation[:32]
        total = _fmt_cts(ligne.total_cts)
        if ligne.quantite > 1:
            buf += f"  {ligne.quantite} x {_fmt_cts(ligne.prix_unitaire_cts)}".encode("cp858") + b'\n'
        buf += _line_two_cols(desig, total).encode("cp858") + b'\n'

    buf += _separator("-").encode("cp858") + b'\n'

    # ── Sous-total HT ────────────────────────────────────────
    if data.sous_total_ht_cts:
        buf += _line_two_cols("Sous-total HT", _fmt_cts(data.sous_total_ht_cts)).encode("cp858") + b'\n'

    # ── TVA ventilation ───────────────────────────────────────
    for tva in data.tva_breakdown:
        buf += _line_two_cols(
            f"TVA {tva.taux_label}",
            _fmt_cts(tva.montant_tva_cts),
        ).encode("cp858") + b'\n'

    # ── Total TTC ─────────────────────────────────────────────
    buf += _separator("=").encode("cp858") + b'\n'
    buf += CMD_BOLD_ON + CMD_DOUBLE_HEIGHT
    buf += CMD_ALIGN_RIGHT
    buf += f"TOTAL  {_fmt_cts(data.total_ttc_cts)} EUR".encode("cp858") + b'\n'
    buf += CMD_NORMAL_SIZE + CMD_BOLD_OFF + CMD_ALIGN_LEFT

    buf += _separator("=").encode("cp858") + b'\n'

    # ── QR code (si URL fournie) ──────────────────────────────
    if data.qr_url:
        # QR code ESC/POS Model 2
        buf += CMD_ALIGN_CENTER
        # Store QR data
        qr_data = data.qr_url.encode("ascii", errors="replace")
        store_len = len(qr_data) + 3
        buf += GS + b'(k' + store_len.to_bytes(2, "little") + b'\x31\x50\x30' + qr_data
        # Set size (module 4)
        buf += GS + b'(k\x03\x00\x31\x43\x04'
        # Set error correction L
        buf += GS + b'(k\x03\x00\x31\x45\x30'
        # Print QR
        buf += GS + b'(k\x03\x00\x31\x51\x30'
        buf += CMD_ALIGN_LEFT
        buf += b'\n'

    # ── Pied ──────────────────────────────────────────────────
    buf += CMD_ALIGN_CENTER
    if data.mention_legale:
        buf += data.mention_legale.encode("cp858", errors="replace") + b'\n'
    buf += CMD_ALIGN_LEFT

    # Feed + cut
    buf += CMD_FEED_LINES + b'\x04'
    buf += CMD_CUT

    # Tiroir-caisse
    if data.ouvrir_tiroir:
        buf += CMD_KICK_DRAWER

    return bytes(buf)


# ── Network send ──────────────────────────────────────────────────────────────


def send_to_printer(
    data: bytes,
    host: str,
    port: int = 9100,
    timeout_seconds: int = 5,
) -> bool:
    """Envoie des bytes ESC/POS vers une imprimante réseau via TCP raw.

    Returns:
        True si envoi réussi, False sinon.
    """
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds) as sock:
            sock.sendall(data)
        logger.info("Ticket sent to %s:%d (%d bytes)", host, port, len(data))
        return True
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        logger.error("Failed to send ticket to %s:%d — %s", host, port, e)
        return False


def print_ticket(data: TicketData, host: str, port: int = 9100) -> bool:
    """Build et envoie un ticket complet."""
    ticket_bytes = build_ticket_bytes(data)
    return send_to_printer(ticket_bytes, host, port)
