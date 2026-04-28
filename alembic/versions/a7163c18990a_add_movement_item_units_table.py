"""add_movement_item_units_table

Revision ID: a7163c18990a
Revises: h4i5j6k7l8m9
Create Date: 2026-02-18 03:55:35.488390

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a7163c18990a'
down_revision: Union[str, None] = 'h4i5j6k7l8m9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('movement_item_units',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('movement_item_id', sa.Integer(), nullable=False, comment='FK ligne de mouvement parente'),
    sa.Column('stock_item_id', sa.Integer(), nullable=False, comment='FK unité de stock physique'),
    sa.Column('condition', sa.String(length=20), nullable=True, comment='État au retour: perfect, good, damaged, missing'),
    sa.Column('condition_notes', sa.Text(), nullable=True, comment="Notes sur l'état de cette unité"),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment="Date de création de l'enregistrement"),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Date de dernière modification'),
    sa.Column('tenant_id', sa.BigInteger(), nullable=False, comment='ID du tenant (organisation cliente)'),
    sa.ForeignKeyConstraint(['movement_item_id'], ['movement_items.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['stock_item_id'], ['stock_items.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_movement_item_unit_stock_item', 'movement_item_units', ['stock_item_id'], unique=False)
    op.create_index('ix_movement_item_unit_tenant_item', 'movement_item_units', ['tenant_id', 'movement_item_id'], unique=False)
    op.create_index(op.f('ix_movement_item_units_tenant_id'), 'movement_item_units', ['tenant_id'], unique=False)

    # Suppression des index stock_items renommés (sans impact données)
    op.drop_index(op.f('ix_stock_items_tenant_product_status'), table_name='stock_items')
    op.drop_index(op.f('ix_stock_items_tenant_reservation'), table_name='stock_items')
    op.create_index(op.f('ix_stock_items_tenant_id'), 'stock_items', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_stock_items_tenant_id'), table_name='stock_items')
    op.create_index(op.f('ix_stock_items_tenant_reservation'), 'stock_items', ['tenant_id', 'current_reservation_id'], unique=False)
    op.create_index(op.f('ix_stock_items_tenant_product_status'), 'stock_items', ['tenant_id', 'product_id', 'status'], unique=False)
    op.drop_index(op.f('ix_movement_item_units_tenant_id'), table_name='movement_item_units')
    op.drop_index('ix_movement_item_unit_tenant_item', table_name='movement_item_units')
    op.drop_index('ix_movement_item_unit_stock_item', table_name='movement_item_units')
    op.drop_table('movement_item_units')


def _unused_downgrade() -> None:
    # Ancien contenu autogénéré — conservé pour référence
    op.alter_column('damage_types', 'id',
               existing_type=sa.BIGINT(),
               type_=sa.Integer(),
               existing_nullable=False,
               autoincrement=True)
    op.alter_column('damage_types', 'name',
               existing_type=sa.VARCHAR(length=100),
               comment='Libellé du type de dommage',
               existing_nullable=False)
    op.alter_column('damage_types', 'default_fee_cents',
               existing_type=sa.BIGINT(),
               comment='Tarif par défaut en centimes (0 = montant à saisir)',
               existing_nullable=False,
               existing_server_default=sa.text("'0'::bigint"))
    op.alter_column('damage_types', 'created_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=sa.DateTime(timezone=True),
               nullable=False,
               comment="Date de création de l'enregistrement")
    op.alter_column('damage_types', 'updated_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=sa.DateTime(timezone=True),
               nullable=False,
               comment='Date de dernière modification')
    op.alter_column('damage_types', 'tenant_id',
               existing_type=sa.BIGINT(),
               comment='ID du tenant (organisation cliente)',
               existing_nullable=False)
    op.alter_column('damage_types', 'is_active',
               existing_type=sa.BOOLEAN(),
               comment='Actif (False = supprimé logiquement)',
               existing_nullable=False,
               existing_server_default=sa.text('true'))
    op.drop_index(op.f('ix_damage_types_tenant'), table_name='damage_types')
    op.create_index(op.f('ix_damage_types_tenant_id'), 'damage_types', ['tenant_id'], unique=False)
    op.alter_column('delivery_zones', 'id',
               existing_type=sa.BIGINT(),
               type_=sa.Integer(),
               existing_nullable=False,
               autoincrement=True)
    op.alter_column('delivery_zones', 'department_code',
               existing_type=sa.VARCHAR(length=3),
               comment="Code INSEE du département (ex: '60' pour Oise)",
               existing_nullable=False)
    op.alter_column('delivery_zones', 'department_name',
               existing_type=sa.VARCHAR(length=100),
               comment='Nom du département',
               existing_nullable=False)
    op.alter_column('delivery_zones', 'delivery_fee_cents',
               existing_type=sa.BIGINT(),
               comment='Tarif livraison de base en centimes (0 = sur devis)',
               existing_nullable=False,
               existing_server_default=sa.text("'0'::bigint"))
    op.alter_column('delivery_zones', 'sunday_surcharge_cents',
               existing_type=sa.BIGINT(),
               comment='Supplément reprise dimanche en centimes',
               existing_nullable=False,
               existing_server_default=sa.text("'0'::bigint"))
    op.alter_column('delivery_zones', 'notes',
               existing_type=sa.TEXT(),
               comment='Informations complémentaires (conditions, distance max…)',
               existing_nullable=True)
    op.alter_column('delivery_zones', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               comment="Date de création de l'enregistrement",
               existing_nullable=False,
               existing_server_default=sa.text('now()'))
    op.alter_column('delivery_zones', 'updated_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               comment='Date de dernière modification',
               existing_nullable=False,
               existing_server_default=sa.text('now()'))
    op.alter_column('delivery_zones', 'tenant_id',
               existing_type=sa.BIGINT(),
               comment='ID du tenant (organisation cliente)',
               existing_nullable=False)
    op.alter_column('delivery_zones', 'is_active',
               existing_type=sa.BOOLEAN(),
               comment='Actif (False = supprimé logiquement)',
               existing_nullable=False,
               existing_server_default=sa.text('true'))
    op.alter_column('deposits', 'id',
               existing_type=sa.BIGINT(),
               type_=sa.Integer(),
               existing_nullable=False,
               autoincrement=True)
    op.alter_column('deposits', 'reservation_id',
               existing_type=sa.BIGINT(),
               comment='FK vers la réservation parente',
               existing_nullable=False)
    op.alter_column('deposits', 'amount_cents',
               existing_type=sa.BIGINT(),
               comment='Montant de la caution en centimes (> 0)',
               existing_nullable=False)
    op.alter_column('deposits', 'status',
               existing_type=sa.VARCHAR(length=20),
               comment='Statut : held, released, retained',
               existing_nullable=False,
               existing_server_default=sa.text("'held'::character varying"))
    op.alter_column('deposits', 'retained_amount_cents',
               existing_type=sa.BIGINT(),
               comment='Montant retenu en centimes (rétention partielle)',
               existing_nullable=True)
    op.alter_column('deposits', 'collection_date',
               existing_type=sa.DATE(),
               comment="Date d'encaissement de la caution",
               existing_nullable=True)
    op.alter_column('deposits', 'release_date',
               existing_type=sa.DATE(),
               comment='Date de restitution de la caution',
               existing_nullable=True)
    op.alter_column('deposits', 'notes',
               existing_type=sa.VARCHAR(length=500),
               comment='Notes libres',
               existing_nullable=True)
    op.alter_column('deposits', 'created_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=sa.DateTime(timezone=True),
               nullable=False,
               comment="Date de création de l'enregistrement")
    op.alter_column('deposits', 'updated_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=sa.DateTime(timezone=True),
               nullable=False,
               comment='Date de dernière modification')
    op.alter_column('deposits', 'tenant_id',
               existing_type=sa.BIGINT(),
               comment='ID du tenant (organisation cliente)',
               existing_nullable=False)
    op.create_index(op.f('ix_deposits_tenant_id'), 'deposits', ['tenant_id'], unique=False)
    op.alter_column('invoice_charges', 'id',
               existing_type=sa.BIGINT(),
               type_=sa.Integer(),
               existing_nullable=False,
               autoincrement=True)
    op.alter_column('invoice_charges', 'invoice_id',
               existing_type=sa.BIGINT(),
               comment='FK vers la facture parente',
               existing_nullable=False)
    op.alter_column('invoice_charges', 'damage_type_id',
               existing_type=sa.BIGINT(),
               comment='FK vers le type de dommage (optionnel)',
               existing_comment='ID du type de dommage (optionnel, Session I)',
               existing_nullable=True)
    op.alter_column('invoice_charges', 'created_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=sa.DateTime(timezone=True),
               nullable=False,
               comment="Date de création de l'enregistrement")
    op.alter_column('invoice_charges', 'updated_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=sa.DateTime(timezone=True),
               nullable=False,
               comment='Date de dernière modification')
    op.alter_column('invoice_charges', 'tenant_id',
               existing_type=sa.BIGINT(),
               comment='ID du tenant (organisation cliente)',
               existing_nullable=False)
    op.create_index(op.f('ix_invoice_charges_tenant_id'), 'invoice_charges', ['tenant_id'], unique=False)
    op.alter_column('movement_items', 'variant_id',
               existing_type=sa.INTEGER(),
               comment='FK variante couleur du produit',
               existing_comment='Variante couleur du produit (remplace product_variation_id)',
               existing_nullable=True)
    op.drop_index(op.f('ix_movement_items_variant_id'), table_name='movement_items')
    op.alter_column('payments', 'id',
               existing_type=sa.BIGINT(),
               type_=sa.Integer(),
               existing_nullable=False,
               autoincrement=True)
    op.alter_column('payments', 'invoice_id',
               existing_type=sa.BIGINT(),
               comment='FK vers la facture parente',
               existing_nullable=False)
    op.alter_column('payments', 'amount_cents',
               existing_type=sa.BIGINT(),
               comment='Montant du paiement en centimes (> 0)',
               existing_nullable=False)
    op.alter_column('payments', 'payment_method',
               existing_type=sa.VARCHAR(length=20),
               comment='Méthode : cash, card, transfer, check',
               existing_nullable=False)
    op.alter_column('payments', 'payment_date',
               existing_type=sa.DATE(),
               comment='Date du paiement',
               existing_nullable=False)
    op.alter_column('payments', 'notes',
               existing_type=sa.VARCHAR(length=500),
               comment='Notes libres',
               existing_nullable=True)
    op.alter_column('payments', 'created_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=sa.DateTime(timezone=True),
               nullable=False,
               comment="Date de création de l'enregistrement")
    op.alter_column('payments', 'updated_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=sa.DateTime(timezone=True),
               nullable=False,
               comment='Date de dernière modification')
    op.alter_column('payments', 'tenant_id',
               existing_type=sa.BIGINT(),
               comment='ID du tenant (organisation cliente)',
               existing_nullable=False)
    op.create_index(op.f('ix_payments_tenant_id'), 'payments', ['tenant_id'], unique=False)
    op.alter_column('product_variants', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               comment="Date de création de l'enregistrement",
               existing_nullable=False,
               existing_server_default=sa.text('now()'))
    op.alter_column('product_variants', 'updated_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               comment='Date de dernière modification',
               existing_nullable=False,
               existing_server_default=sa.text('now()'))
    op.alter_column('product_variants', 'tenant_id',
               existing_type=sa.INTEGER(),
               type_=sa.BigInteger(),
               comment='ID du tenant (organisation cliente)',
               existing_nullable=False)
    op.alter_column('product_variants', 'is_active',
               existing_type=sa.BOOLEAN(),
               comment='Actif (False = supprimé logiquement)',
               existing_nullable=False,
               existing_server_default=sa.text('true'))
    op.alter_column('products', 'cleaning_fee',
               existing_type=sa.BIGINT(),
               comment='Frais de nettoyage en centimes (0 = inclus dans le prix, règle marveline.fr)',
               existing_comment='Frais de nettoyage en centimes (0 = inclus dans le prix)',
               existing_nullable=False,
               existing_server_default=sa.text("'0'::bigint"))
    op.alter_column('reservation_lines', 'variant_id',
               existing_type=sa.INTEGER(),
               comment='ID de la variante couleur choisie',
               existing_comment='Variante couleur choisie (nullable si produit sans variantes)',
               existing_nullable=True)
    op.alter_column('reservations', 'event_name',
               existing_type=sa.VARCHAR(length=200),
               comment="Nom de l'événement",
               existing_comment="Nom de l'événement (ex: Mariage Dupont)",
               existing_nullable=True)
    op.alter_column('reservations', 'guest_count',
               existing_type=sa.INTEGER(),
               comment="Nombre d'invités",
               existing_comment="Nombre d'invités (doit être > 0)",
               existing_nullable=True)
    op.alter_column('stock_items', 'id',
               existing_type=sa.BIGINT(),
               type_=sa.Integer(),
               existing_nullable=False,
               autoincrement=True)
    op.alter_column('stock_items', 'product_id',
               existing_type=sa.BIGINT(),
               comment='Produit auquel appartient cette unité',
               existing_nullable=False)
    op.alter_column('stock_items', 'serial_number',
               existing_type=sa.VARCHAR(length=100),
               comment='Numéro de série optionnel',
               existing_nullable=True)
    op.alter_column('stock_items', 'status',
               existing_type=sa.VARCHAR(length=20),
               comment='État courant : available|reserved|on_location|damaged|in_repair|retired',
               existing_nullable=False,
               existing_server_default=sa.text("'available'::character varying"))
    op.alter_column('stock_items', 'current_reservation_id',
               existing_type=sa.BIGINT(),
               comment='Réservation en cours (nullable)',
               existing_nullable=True)
    op.alter_column('stock_items', 'notes',
               existing_type=sa.TEXT(),
               comment="Notes libres sur l'unité",
               existing_nullable=True)
    op.alter_column('stock_items', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               comment="Date de création de l'enregistrement",
               existing_nullable=False,
               existing_server_default=sa.text('now()'))
    op.alter_column('stock_items', 'updated_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               comment='Date de dernière modification',
               existing_nullable=False,
               existing_server_default=sa.text('now()'))
    op.alter_column('stock_items', 'tenant_id',
               existing_type=sa.BIGINT(),
               comment='ID du tenant (organisation cliente)',
               existing_nullable=False)
    op.drop_index(op.f('ix_stock_items_tenant_product_status'), table_name='stock_items')
    op.drop_index(op.f('ix_stock_items_tenant_reservation'), table_name='stock_items')
    op.create_index(op.f('ix_stock_items_tenant_id'), 'stock_items', ['tenant_id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_stock_items_tenant_id'), table_name='stock_items')
    op.create_index(op.f('ix_stock_items_tenant_reservation'), 'stock_items', ['tenant_id', 'current_reservation_id'], unique=False)
    op.create_index(op.f('ix_stock_items_tenant_product_status'), 'stock_items', ['tenant_id', 'product_id', 'status'], unique=False)
    op.alter_column('stock_items', 'tenant_id',
               existing_type=sa.BIGINT(),
               comment=None,
               existing_comment='ID du tenant (organisation cliente)',
               existing_nullable=False)
    op.alter_column('stock_items', 'updated_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               comment=None,
               existing_comment='Date de dernière modification',
               existing_nullable=False,
               existing_server_default=sa.text('now()'))
    op.alter_column('stock_items', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               comment=None,
               existing_comment="Date de création de l'enregistrement",
               existing_nullable=False,
               existing_server_default=sa.text('now()'))
    op.alter_column('stock_items', 'notes',
               existing_type=sa.TEXT(),
               comment=None,
               existing_comment="Notes libres sur l'unité",
               existing_nullable=True)
    op.alter_column('stock_items', 'current_reservation_id',
               existing_type=sa.BIGINT(),
               comment=None,
               existing_comment='Réservation en cours (nullable)',
               existing_nullable=True)
    op.alter_column('stock_items', 'status',
               existing_type=sa.VARCHAR(length=20),
               comment=None,
               existing_comment='État courant : available|reserved|on_location|damaged|in_repair|retired',
               existing_nullable=False,
               existing_server_default=sa.text("'available'::character varying"))
    op.alter_column('stock_items', 'serial_number',
               existing_type=sa.VARCHAR(length=100),
               comment=None,
               existing_comment='Numéro de série optionnel',
               existing_nullable=True)
    op.alter_column('stock_items', 'product_id',
               existing_type=sa.BIGINT(),
               comment=None,
               existing_comment='Produit auquel appartient cette unité',
               existing_nullable=False)
    op.alter_column('stock_items', 'id',
               existing_type=sa.Integer(),
               type_=sa.BIGINT(),
               existing_nullable=False,
               autoincrement=True)
    op.alter_column('reservations', 'guest_count',
               existing_type=sa.INTEGER(),
               comment="Nombre d'invités (doit être > 0)",
               existing_comment="Nombre d'invités",
               existing_nullable=True)
    op.alter_column('reservations', 'event_name',
               existing_type=sa.VARCHAR(length=200),
               comment="Nom de l'événement (ex: Mariage Dupont)",
               existing_comment="Nom de l'événement",
               existing_nullable=True)
    op.alter_column('reservation_lines', 'variant_id',
               existing_type=sa.INTEGER(),
               comment='Variante couleur choisie (nullable si produit sans variantes)',
               existing_comment='ID de la variante couleur choisie',
               existing_nullable=True)
    op.alter_column('products', 'cleaning_fee',
               existing_type=sa.BIGINT(),
               comment='Frais de nettoyage en centimes (0 = inclus dans le prix)',
               existing_comment='Frais de nettoyage en centimes (0 = inclus dans le prix, règle marveline.fr)',
               existing_nullable=False,
               existing_server_default=sa.text("'0'::bigint"))
    op.alter_column('product_variants', 'is_active',
               existing_type=sa.BOOLEAN(),
               comment=None,
               existing_comment='Actif (False = supprimé logiquement)',
               existing_nullable=False,
               existing_server_default=sa.text('true'))
    op.alter_column('product_variants', 'tenant_id',
               existing_type=sa.BigInteger(),
               type_=sa.INTEGER(),
               comment=None,
               existing_comment='ID du tenant (organisation cliente)',
               existing_nullable=False)
    op.alter_column('product_variants', 'updated_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               comment=None,
               existing_comment='Date de dernière modification',
               existing_nullable=False,
               existing_server_default=sa.text('now()'))
    op.alter_column('product_variants', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               comment=None,
               existing_comment="Date de création de l'enregistrement",
               existing_nullable=False,
               existing_server_default=sa.text('now()'))
    op.drop_index(op.f('ix_payments_tenant_id'), table_name='payments')
    op.alter_column('payments', 'tenant_id',
               existing_type=sa.BIGINT(),
               comment=None,
               existing_comment='ID du tenant (organisation cliente)',
               existing_nullable=False)
    op.alter_column('payments', 'updated_at',
               existing_type=sa.DateTime(timezone=True),
               type_=postgresql.TIMESTAMP(),
               nullable=True,
               comment=None,
               existing_comment='Date de dernière modification')
    op.alter_column('payments', 'created_at',
               existing_type=sa.DateTime(timezone=True),
               type_=postgresql.TIMESTAMP(),
               nullable=True,
               comment=None,
               existing_comment="Date de création de l'enregistrement")
    op.alter_column('payments', 'notes',
               existing_type=sa.VARCHAR(length=500),
               comment=None,
               existing_comment='Notes libres',
               existing_nullable=True)
    op.alter_column('payments', 'payment_date',
               existing_type=sa.DATE(),
               comment=None,
               existing_comment='Date du paiement',
               existing_nullable=False)
    op.alter_column('payments', 'payment_method',
               existing_type=sa.VARCHAR(length=20),
               comment=None,
               existing_comment='Méthode : cash, card, transfer, check',
               existing_nullable=False)
    op.alter_column('payments', 'amount_cents',
               existing_type=sa.BIGINT(),
               comment=None,
               existing_comment='Montant du paiement en centimes (> 0)',
               existing_nullable=False)
    op.alter_column('payments', 'invoice_id',
               existing_type=sa.BIGINT(),
               comment=None,
               existing_comment='FK vers la facture parente',
               existing_nullable=False)
    op.alter_column('payments', 'id',
               existing_type=sa.Integer(),
               type_=sa.BIGINT(),
               existing_nullable=False,
               autoincrement=True)
    op.create_index(op.f('ix_movement_items_variant_id'), 'movement_items', ['variant_id'], unique=False)
    op.alter_column('movement_items', 'variant_id',
               existing_type=sa.INTEGER(),
               comment='Variante couleur du produit (remplace product_variation_id)',
               existing_comment='FK variante couleur du produit',
               existing_nullable=True)
    op.drop_index(op.f('ix_invoice_charges_tenant_id'), table_name='invoice_charges')
    op.alter_column('invoice_charges', 'tenant_id',
               existing_type=sa.BIGINT(),
               comment=None,
               existing_comment='ID du tenant (organisation cliente)',
               existing_nullable=False)
    op.alter_column('invoice_charges', 'updated_at',
               existing_type=sa.DateTime(timezone=True),
               type_=postgresql.TIMESTAMP(),
               nullable=True,
               comment=None,
               existing_comment='Date de dernière modification')
    op.alter_column('invoice_charges', 'created_at',
               existing_type=sa.DateTime(timezone=True),
               type_=postgresql.TIMESTAMP(),
               nullable=True,
               comment=None,
               existing_comment="Date de création de l'enregistrement")
    op.alter_column('invoice_charges', 'damage_type_id',
               existing_type=sa.BIGINT(),
               comment='ID du type de dommage (optionnel, Session I)',
               existing_comment='FK vers le type de dommage (optionnel)',
               existing_nullable=True)
    op.alter_column('invoice_charges', 'invoice_id',
               existing_type=sa.BIGINT(),
               comment=None,
               existing_comment='FK vers la facture parente',
               existing_nullable=False)
    op.alter_column('invoice_charges', 'id',
               existing_type=sa.Integer(),
               type_=sa.BIGINT(),
               existing_nullable=False,
               autoincrement=True)
    op.drop_index(op.f('ix_deposits_tenant_id'), table_name='deposits')
    op.alter_column('deposits', 'tenant_id',
               existing_type=sa.BIGINT(),
               comment=None,
               existing_comment='ID du tenant (organisation cliente)',
               existing_nullable=False)
    op.alter_column('deposits', 'updated_at',
               existing_type=sa.DateTime(timezone=True),
               type_=postgresql.TIMESTAMP(),
               nullable=True,
               comment=None,
               existing_comment='Date de dernière modification')
    op.alter_column('deposits', 'created_at',
               existing_type=sa.DateTime(timezone=True),
               type_=postgresql.TIMESTAMP(),
               nullable=True,
               comment=None,
               existing_comment="Date de création de l'enregistrement")
    op.alter_column('deposits', 'notes',
               existing_type=sa.VARCHAR(length=500),
               comment=None,
               existing_comment='Notes libres',
               existing_nullable=True)
    op.alter_column('deposits', 'release_date',
               existing_type=sa.DATE(),
               comment=None,
               existing_comment='Date de restitution de la caution',
               existing_nullable=True)
    op.alter_column('deposits', 'collection_date',
               existing_type=sa.DATE(),
               comment=None,
               existing_comment="Date d'encaissement de la caution",
               existing_nullable=True)
    op.alter_column('deposits', 'retained_amount_cents',
               existing_type=sa.BIGINT(),
               comment=None,
               existing_comment='Montant retenu en centimes (rétention partielle)',
               existing_nullable=True)
    op.alter_column('deposits', 'status',
               existing_type=sa.VARCHAR(length=20),
               comment=None,
               existing_comment='Statut : held, released, retained',
               existing_nullable=False,
               existing_server_default=sa.text("'held'::character varying"))
    op.alter_column('deposits', 'amount_cents',
               existing_type=sa.BIGINT(),
               comment=None,
               existing_comment='Montant de la caution en centimes (> 0)',
               existing_nullable=False)
    op.alter_column('deposits', 'reservation_id',
               existing_type=sa.BIGINT(),
               comment=None,
               existing_comment='FK vers la réservation parente',
               existing_nullable=False)
    op.alter_column('deposits', 'id',
               existing_type=sa.Integer(),
               type_=sa.BIGINT(),
               existing_nullable=False,
               autoincrement=True)
    op.alter_column('delivery_zones', 'is_active',
               existing_type=sa.BOOLEAN(),
               comment=None,
               existing_comment='Actif (False = supprimé logiquement)',
               existing_nullable=False,
               existing_server_default=sa.text('true'))
    op.alter_column('delivery_zones', 'tenant_id',
               existing_type=sa.BIGINT(),
               comment=None,
               existing_comment='ID du tenant (organisation cliente)',
               existing_nullable=False)
    op.alter_column('delivery_zones', 'updated_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               comment=None,
               existing_comment='Date de dernière modification',
               existing_nullable=False,
               existing_server_default=sa.text('now()'))
    op.alter_column('delivery_zones', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               comment=None,
               existing_comment="Date de création de l'enregistrement",
               existing_nullable=False,
               existing_server_default=sa.text('now()'))
    op.alter_column('delivery_zones', 'notes',
               existing_type=sa.TEXT(),
               comment=None,
               existing_comment='Informations complémentaires (conditions, distance max…)',
               existing_nullable=True)
    op.alter_column('delivery_zones', 'sunday_surcharge_cents',
               existing_type=sa.BIGINT(),
               comment=None,
               existing_comment='Supplément reprise dimanche en centimes',
               existing_nullable=False,
               existing_server_default=sa.text("'0'::bigint"))
    op.alter_column('delivery_zones', 'delivery_fee_cents',
               existing_type=sa.BIGINT(),
               comment=None,
               existing_comment='Tarif livraison de base en centimes (0 = sur devis)',
               existing_nullable=False,
               existing_server_default=sa.text("'0'::bigint"))
    op.alter_column('delivery_zones', 'department_name',
               existing_type=sa.VARCHAR(length=100),
               comment=None,
               existing_comment='Nom du département',
               existing_nullable=False)
    op.alter_column('delivery_zones', 'department_code',
               existing_type=sa.VARCHAR(length=3),
               comment=None,
               existing_comment="Code INSEE du département (ex: '60' pour Oise)",
               existing_nullable=False)
    op.alter_column('delivery_zones', 'id',
               existing_type=sa.Integer(),
               type_=sa.BIGINT(),
               existing_nullable=False,
               autoincrement=True)
    op.drop_index(op.f('ix_damage_types_tenant_id'), table_name='damage_types')
    op.create_index(op.f('ix_damage_types_tenant'), 'damage_types', ['tenant_id'], unique=False)
    op.alter_column('damage_types', 'is_active',
               existing_type=sa.BOOLEAN(),
               comment=None,
               existing_comment='Actif (False = supprimé logiquement)',
               existing_nullable=False,
               existing_server_default=sa.text('true'))
    op.alter_column('damage_types', 'tenant_id',
               existing_type=sa.BIGINT(),
               comment=None,
               existing_comment='ID du tenant (organisation cliente)',
               existing_nullable=False)
    op.alter_column('damage_types', 'updated_at',
               existing_type=sa.DateTime(timezone=True),
               type_=postgresql.TIMESTAMP(),
               nullable=True,
               comment=None,
               existing_comment='Date de dernière modification')
    op.alter_column('damage_types', 'created_at',
               existing_type=sa.DateTime(timezone=True),
               type_=postgresql.TIMESTAMP(),
               nullable=True,
               comment=None,
               existing_comment="Date de création de l'enregistrement")
    op.alter_column('damage_types', 'default_fee_cents',
               existing_type=sa.BIGINT(),
               comment=None,
               existing_comment='Tarif par défaut en centimes (0 = montant à saisir)',
               existing_nullable=False,
               existing_server_default=sa.text("'0'::bigint"))
    op.alter_column('damage_types', 'name',
               existing_type=sa.VARCHAR(length=100),
               comment=None,
               existing_comment='Libellé du type de dommage',
               existing_nullable=False)
    op.alter_column('damage_types', 'id',
               existing_type=sa.Integer(),
               type_=sa.BIGINT(),
               existing_nullable=False,
               autoincrement=True)
    op.drop_index(op.f('ix_movement_item_units_tenant_id'), table_name='movement_item_units')
    op.drop_index('ix_movement_item_unit_tenant_item', table_name='movement_item_units')
    op.drop_index('ix_movement_item_unit_stock_item', table_name='movement_item_units')
    op.drop_table('movement_item_units')
    # ### end Alembic commands ###
