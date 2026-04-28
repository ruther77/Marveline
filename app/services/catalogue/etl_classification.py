"""Classifier catégories alimentaires par keywords pour le pipeline ETL (M05).

Assigne un code parmi les 91 définis dans categories_epicerie.sql à partir
de la désignation normalisée d'un produit catalogue.

La designation_norm est déjà normalisée via normalize_designation() :
    NFD→ASCII, lowercase, stop words (le/la/les/de/du/…), truncate 80 chars.

Stratégie : liste ordonnée de règles (keywords → code). Premier match gagne.
Fallback : 'AUTRE'.

Usage :
    code = classify_categorie_code("steak hache surgele")  # → "SURG_VIANDE"
    code = classify_categorie_code("riz basmati long")     # → "EPIC_RIZ"
"""
from __future__ import annotations

from app.services.catalogue.etl_deduplication import compute_similarity

_FALLBACK_CODE = "AUTRE"

_KNN_SEUIL: float = 0.80
"""Seuil Jaro-Winkler minimum pour propager une catégorie par KNN (k=1).
En dessous, on retourne AUTRE plutôt que de propager une classification incertaine."""

# Chaque tuple : (liste de sous-chaînes cherchées dans designation_norm, code)
# Ordre = priorité — règles spécifiques en premier.
_RULES: list[tuple[list[str], str]] = [
    # ── Surgelés (avant catégories fraiches homonymes) ───────────────────────
    (["steak hache surgele", "viande hachee surgele",
      "burger surgele", "steak surgele"], "SURG_VIANDE"),
    (["poisson surgele", "baton poisson", "filet poisson surgele",
      "crevette surgele", "cabillaud surgele", "saumon surgele",
      "paella surgele", "surimi"], "SURG_POISSON"),
    (["glace", "sorbet", "esquimau", "cornetto", "magnum",
      "bac glace", "fontaine glace", "fontaines glaces",
      "freeze giant", "cg vanille", "mr freeze"], "SURG_GLACE"),
    (["tarte surgele", "feuillete surgele", "quiche surgele",
      "pain surgele", "viennoiserie surgelee",
      "croissant surgele", "brioche surgelee",
      "pizza ristorante", "pizza rustica",
      "nem porc", "frite country", "frite bistro",
      "mccain", "lambweston", "ziggy fries", "fry n dip"], "SURG_PATISS"),
    (["legume surgele", "petits pois surgele", "epinard surgele",
      "ratatouille surgele", "poele legume", "haricot vert surgele",
      "brocoli surgele", "chou fleur surgele", "surgele",
      "ail frais surg", "oseille surg", "menthe douce surg",
      "ciboulette frai surg"], "SURG_LEGUME"),

    # ── Charcuterie fine (avant catégories viandes fraiches) ─────────────────
    (["lardons", "allumettes lard"], "FRAIS_LARDON"),
    (["saucisson", "rosette", "chorizo", "rillette", "pate campagne",
      "terrine", "mousse canard", "foie gras", "rillons",
      "coppa", "bresaola", "pancetta",
      "fuet geant", "fuet", "scisson sec",
      "allumette fum", "allumette nature",
      "mortadelle", "fgras canard", "cachir",
      "oig charc"], "FRAIS_CHARC"),
    (["saucisse", "chipolata", "merguez", "knack", "francfort",
      "strasbourg", "cocktail saucisse", "boudin",
      "hot dog", "bockwurst", "sadlami", "scisse"], "FRAIS_SAUCISSE"),
    (["jambon cuit", "jambon blanc", "jambon superieur",
      "jambon paris", "jambon sec", "jambon cru",
      "prosciutto", "serrano",
      "tranchette jb cuit", "tranchette jambon",
      "jb cuit torchon", "jb choix",
      "jb foret noire"], "FRAIS_JAMBON"),

    # ── Conserves (avant produits frais homonymes) ───────────────────────────
    (["concentre tomate", "concentre tom", "coulis tomate", "sauce tomate",
      "tomate concassee", "pulpe tomate", "passata"], "CONS_SAUCE"),
    (["thon boite", "sardine conserve", "maquereau conserve",
      "anchois conserve", "saumon conserve",
      "poisson boite", "hareng conserve",
      # TAIYAT — conserves poisson import
      "sardine huile", "sardine anny",
      "pinton", "pate sardinelle"], "CONS_POISSON"),
    (["cassoulet", "ravioli boite", "chili conserve",
      "plat cuisin", "ratatouille boite", "petit sale",
      "haricot blanc boite", "lentille boite",
      "sandwich", "sandw", "burger", "kebab",
      "tortilla", "wrap", "snack", "cocktail snack",
      "bouchee restau", "croque", "padin sp croque",
      "repas comp"], "CONS_PLAT"),
    (["tomate boite", "mais boite", "haricot vert boite",
      "petits pois boite", "champignon boite", "poivron boite",
      "artichaut conserve", "betterave conserve",
      "asperge conserve", "endive conserve",
      "tomate concassee", "haricots rges", "haricots verts",
      "trio poivron", "mais", "roch mais",
      "roch haricot", "epinard", "epinards hache",
      "olive verte", "olive noire", "oliv vert", "oliv noire",
      "olives vertes", "olives noire",
      "cornichon", "capre",
      "ail blanc", "ail pele", "chou rouge", "chp pied",
      "fond arti", "oliv noir", "oliv noir denoy"], "CONS_LEGUME"),

    # ── Alcools — keywords courts pour factures METRO ────────────────────────
    (["biere", "beer", "pils", "lager", "ipa", "stout",
      "weiss", "brasserie", "pack biere", "canette biere",
      "brun", "blonde biere", "ledffe", "leffe",
      "guiness irlande", "heineken", "castel", "flag",
      "33 export", "beaufort"], "ALC_BIERE"),
    # Rosé AVANT rouge (sinon les keywords rouge matchent les rosés)
    (["vin rose", "rose sec", "provence rose", "tavel",
      "rse mil", "rse maurin", "rse c.", "oceade rse",
      "anjou rse", "igp rse", "cdp rse",
      "cab anjou rse", "igp med rse", "igdp med rse", "atlantiq igp oceade rse",
      "rose anjou"], "ALC_VIN_ROSE"),
    # Blanc AVANT rouge (chardonnay = blanc)
    (["vin blanc", "chardonnay", "sauvignon blanc", "muscadet",
      "riesling", "chablis", "sancerre", "alsace blanc",
      "pouilly fume", "viognier", "gewurztraminer",
      "chardon", "ribeaupierre", "ribeaup",
      "igdp med blanc", "igp med blanc",
      "romet blanc", "ita blc"], "ALC_VIN_BLC"),
    (["vin rouge", "bordeaux rouge", "cote rhone rouge",
      "beaujolais", "merlot", "cabernet", "pinot noir",
      "saint emilion", "st emilion", "st em mil",
      "bourgogne rouge", "chateauneuf",
      "cotes rhone", "bordeaux", "medoc", "paysoc",
      "pays oc", "igp med", "monbazil",
      "mil mondesir", "murail", "maures", "bergerie",
      "margaux", "pauillac", "pomerol", "haut medoc", "ht med",
      "graves", "fronsac", "lalande", "lussac",
      "moulis", "listrac", "cotes bordeaux",
      "pom bal", "mouton cad", "labegorce",
      "mgx aoc", "igdp med", "maucaill moul",
      "paveil luze", "clement pichon",
      "fugue nenin", "giscours",
      "lamoth joub", "ladmoth", "tour prignac",
      "chinian", "ventoux", "gaillac",
      "arguille mil", "buzet mil"], "ALC_VIN_RGE"),
    (["champagne", "prosecco", "cava", "cremant",
      "mousseux", "petillant", "champ"], "ALC_APERO"),
    (["whisky", "whiskey", "bourbon", "scotch", "cognac",
      "armagnac", "calvados", "rhum", "rh mauny", "rh la mauny",
      "rhum dillon", "rhum stjames",
      "tequila", "vodka",
      "gin gibsons", "gin beefeater", "gin bombay", "gin hendrick",
      "gin tanqueray", "marc", "eau vie", "pastis", "absinthe",
      "grappa", "schnaps", "picon", "3riviere",
      "jdaniel", "jdaniels", "jack daniel",
      "campari", "get 27", "get 31",
      "rh stjames", "past box", "past s p",
      "past 8 12", "rhdum"], "ALC_SPIRITUEUX"),
    (["liqueur", "baileys", "cointreau", "triple sec",
      "amaretto", "limoncello", "chartreuse", "benedictine",
      "grand marnier", "drambuie"], "ALC_LIQUEUR"),
    (["aperitif", "martini", "porto", "sherry", "muscat",
      "vermouth", "sangria", "cidre", "pommeau",
      "campari soda"], "ALC_APERO"),

    # ── Boissons sans alcool ─────────────────────────────────────────────────
    (["eau minerale", "eau plate", "eau gazeuse", "perrier",
      "evian", "volvic", "badoit", "vittel", "cristaline",
      "saint yorre", "eau source", "roches ecrins", "roche ecrins",
      "roche des ecrins", "roches des ecrins",
      "eau cristal", "hepar", "contrex", "mont roucous",
      "thonon", "spa reine", "san pell", "san pellegrino",
      "pedrrier", "roche ec"], "BOIS_EAU"),
    (["soda", "coca cola", "coca-cola", "coca colas", "cocacola", "coca d",
      "codca cola", "codca-cola", "coca sans sucr",
      "pepsi", "sprite", "fanta", "7up",
      "schweppes", "orangina", "limonade", "tonic",
      "ginger ale", "ice tea", "energy soda",
      "hawai tropical", "mogu", "oasis", "oasi",
      "tropico", "pulpe", "rioba boiss",
      "scdhweppe", "oadsis", "surfizz",
      # TAIYAT — boissons maltées non-alcoolisées
      "malta guiness", "vita malt", "ginger beer soda"], "BOIS_SODA"),
    (["jus fruit", "nectar", "jus orange", "jus pomme",
      "jus tomate", "jus ananas", "jus raisin",
      "multivitamine", "smoothie", "jus tropical",
      "nectar mangue", "jus abricot",
      "granini", "caraibos", "nect abricot", "nect mangue",
      "danao", "pur jus", "pj ananas", "abc ananas",
      "abc orange", "y-fruits", "baiko",
      # TAIYAT — jus import
      "capri sun", "capri-sun", "caprisun",
      "attot jus", "boisson tamarin",
      "ghanafresh", "praise"], "BOIS_JUS"),
    (["sirop", "grenadine", "eau fleur orang",
      "topping caramel", "topping chocolat",
      "pulco"], "BOIS_SIROP"),
    (["energy drink", "redbull", "redd bull", "red bull",
      "monster energy", "rockstar",
      "boisson energisante", "power drink",
      "crazy tiger"], "BOIS_ENERG"),
    (["cafe", "expresso", "cappuccino", "cafe soluble",
      "nespresso", "ristretto", "dolce gusto", "dolcegusto", "senseo",
      "cafe grain", "cafe moulu", "cafe instantane",
      "espresso forza", "l or espresso"], "BOIS_CAFE"),
    (["infusion", "tisane", "camomille", "verveine",
      "rooibos", "the vert", "the noir", "the blanc",
      "mate"], "BOIS_THE"),
    (["chocolat chaud", "cacao poudre boisson", "nesquik",
      "ovomaltine", "chocolat instant", "poudre cacao lait"], "BOIS_CHOCO"),

    # ── Produits laitiers (creme avant lait) ─────────────────────────────────
    (["creme fraiche", "creme liquide", "creme entiere",
      "creme epaisse", "creme semi", "creme cuisine",
      "creme legere", "creme frai ep", "creme frai.",
      "creme uht", "creme balsa"], "LAIT_CREME"),
    (["beurre doux", "beurre sale", "beurre leger",
      "beurre allege", "beurre demi", "margarine",
      "beurre dx", "beurre tendre", "beurre ds",
      "planta fin", "fruit dor"], "LAIT_BEURRE"),
    (["fromage", "camembert", "brie", "comte", "emmental",
      "gruyere", "cheddar", "roquefort", "mozzarella",
      "parmesan", "feta", "raclette", "reblochon",
      "saint nectaire", "maroilles", "cantal", "mimolette",
      "gouda", "edam", "ricotta", "mascarpone", "brousse",
      "fromage blanc", "petit suisse", "faisselle",
      "boursin", "tartare fromage", "vache qui rit",
      "tome", "munster", "livarot", "epoisses",
      "chevre buche", "chevre fondant",
      "neufchatel", "shd oblon"], "LAIT_FROMAGE"),
    (["yaourt", "yogurt", "yop", "kefir", "lassi",
      "bifidus", "activia", "actimel", "skyr"], "LAIT_YAOURT"),
    (["flan", "creme dessert", "mousse lactee", "riz lait",
      "dessert lacte", "creme brulee", "danette",
      "liegeois", "tiramisu lacte", "tiramisu",
      "panna cotta", "moell coeur", "p tit creamy"], "LAIT_DESSERT"),
    (["lait uht", "lait entier", "lait demi", "lait ecreme",
      "lait pasteurise", "lait vache", "lait brebis",
      "lait chevre", "lait concentre", "lait poudre",
      "boisson vegetale", "lait soja", "lait amande",
      "lait avoine", "lait conc", "lait pdr",
      "alpro", "ladit",
      # TAIYAT — laits marques africaines
      "lait viva", "bonnet rouge", "lait bonnet",
      "lait vrai", "lait concentre"], "LAIT_UHT"),

    # ── Condiments (du plus spécifique au moins) ─────────────────────────────
    (["bouillon cube", "fond veau", "fond volaille",
      "fond boeuf", "bouillon poulet", "bouillon legume",
      "marmite bouillon", "fond sauce", "jus roti",
      # TAIYAT — bouillons import
      "bouillon boeuf", "bouillon poule",
      "maggi cube", "maggi tablette",
      "jumbo bouillon", "jumbo tablette",
      "cube tablette aroma"], "COND_BOUILLON"),
    (["sel fin", "sel gros", "sel iode", "fleur sel",
      "sel mer", "sel himalaya", "gro sel",
      "mediteran", "sel moulin"], "COND_SEL"),
    (["huile olive", "huile tournesol", "huile colza",
      "huile arachide", "huile sesame", "huile pepins",
      "huile friture", "huile vegetale", "hle tournesol",
      "maurel tourneso", "maurel tournesol", "huil tournesol", "hudile tournesol",
      "graisse canard", "graisse oie", "saindoux",
      "friture", "ondosol", "lesieur"], "COND_HUILE"),
    (["vinaigre balsamique", "vinaigre blanc", "vinaigre cidre",
      "vinaigre vin", "vinaigre framboise",
      "vinaigre xeres", "vinaig"], "COND_VINAIGRE"),
    (["ketchup", "mayonnaise", "mayo", "moutarde", "vinaigrette",
      "sauce barbecue", "sauce worcestershire",
      "sauce cocktail", "sauce burger", "sauce cesar",
      "sauce tartare", "sauce ranch", "sauce nuoc",
      "sauce piquante", "harissa sauce",
      "sauce soja claire", "sauce samourai",
      "mayo allegee", "mayonaise",
      "sauce salade", "condiment blanc",
      "arome maggi", "maggi arome", "arome familial"], "COND_SAUCE"),
    (["poivre", "paprika", "curcuma", "cumin", "coriandre poudre",
      "canelle", "gingembre poudre", "piment", "curry",
      "massale", "epice", "noix muscade", "cardamome",
      "anis etoile", "fenugrec", "herbe provence",
      "bouquet garni", "laurier sech", "thym sech",
      "romarin sech", "origan sech", "basilic poudre",
      "ciboulette sch", "ail poudre", "oignon poudre",
      "ras hanout", "colombo", "berbere melange",
      "4 epices", "cinq baies",
      "aidl poudre", "ail semoule",
      "girofle", "clou girofle", "badiane", "vanille gousse",
      "muscade entiere", "poivre vert", "poivre rouge"], "COND_EPICE"),

    # ── Épicerie salée — féculents ────────────────────────────────────────────
    (["couscous", "semoule couscous", "boulgour", "polenta",
      "semoule fine", "semoule dur"], "EPIC_SEMOULE"),
    (["lentille", "pois chiche", "haricot sec", "flageolet",
      "feve", "pois casse", "soja sec", "niebe",
      "mungo",
      # TAIYAT — haricots import
      "haricots blancs", "haricots rouge", "haricots rouges",
      "haricot goma", "haricot vert goma",
      "coco rouge"], "EPIC_LEGUM_SEC"),
    (["spaghetti", "penne", "fusilli", "tagliatelle",
      "lasagne", "gnocchi", "farfalle", "rigatoni",
      "macaroni", "vermicelle pate", "conchiglie",
      "linguine", "tortellini", "pate alimentaire",
      "cheveux ange"], "EPIC_PATE"),
    (["riz basmati", "riz long", "riz rond", "riz jasmin",
      "riz thai", "riz arborio", "riz sauvage",
      "riz complet", "riz blanc", "riz cantonais",
      "riz parfume", "riz monde", "riz parf", "ridz parf"], "EPIC_RIZ"),

    # ── Épicerie sucrée — du plus spécifique au moins ────────────────────────
    (["levure chimique", "levure boulanger",
      "bicarbonate alimentaire"], "SUCR_LEVURE"),
    (["arome vanille", "extrait vanille", "arome amande",
      "colorant alimentaire", "essence citron",
      "rhum patissier", "kirsch patisserie"], "SUCR_AROME"),
    (["nappage", "fondant patissier", "pate amande",
      "perle sucre", "decoration gateau", "ganache"], "SUCR_NAPPAGE"),
    (["farine ble", "farine complete", "farine riz",
      "farine epeautre", "farine mais", "farine sarrasin",
      "fecule", "maizena", "farine patisserie",
      "farine brioche", "farine", "semoul", "semoule",
      "sdemoul", "pate sablee",
      # TAIYAT — sucres
      "sucre poudre", "sucre morceau", "sucre morceaux",
      "saint louis", "sucre glace", "sucre cane"], "SUCR_FARINE"),
    (["cereale petit", "corn flakes", "muesli", "granola",
      "flocon avoine", "porridge", "pop cereale",
      "chocapic", "frosties", "cereales lion", "cereales"], "SUCR_CEREAL"),
    (["confiture", "marmelade", "gelee fruit", "sirop erable",
      "pate tartiner", "nutella", "pralin",
      "beurre cacahuete", "tahini", "speculoos",
      "pate noisette", "miel", "mel cj"], "SUCR_CONF"),
    (["sucre roux", "sucre blanc", "cassonade", "vergeoise",
      "sucre glace", "sucre vanille", "stevia",
      "sucre complet", "sucre cristal", "sucre canne",
      "buchette sucre", "buchette c3",
      "sucre buchette", "sucre solneige", "solneige",
      "perruc buchet", "la perruc"], "SUCR_SUCRE"),
    (["chocolat noir", "tablette chocolat", "chocolat lait",
      "chocolat blanc", "pralinoise", "nestle dessert",
      "cacao poudre", "poudre cacao",
      "toblerone", "cote dor", "petit ecolier choc",
      "lisa cop choc", "milka", "choc patissier",
      "aro choc"], "SUCR_CHOCO"),
    (["bonbon", "caramel bonbon", "chamallow", "haribo",
      "dragee", "sucette", "chewing gum",
      "marshmallow", "ferrero rocher", "ferrero collection",
      "raffaello", "kinder",
      "tarte noix coco",
      "maltesers", "m m s", "m&m", "m s peanut", "dragibus", "schtroumpf",
      "chupa chups", "happy life", "tache langue",
      "tagada", "zan", "carambar", "mentos", "tic tac",
      "reglisse", "fraise tagada", "crocodile haribo",
      "crocodiles sac",
      "nounours haribo", "tubble gum",
      "malabar", "bounty", "kit kat", "kitkat",
      "balisto", "skittles", "freedent", "freed",
      "stimorol", "airwaves", "maoam", "chocobox",
      "unicorn dipper", "bubble nroll", "bubbliz",
      "suc rock fruit", "hollywood chloro", "hwd style", "hwd dr", "madlabar",
      "twix", "snickers", "mars barre", "lion peanut",
      "crocopik", "croco acide", "roch crocodile",
      "love pik", "world mix", "tubo mad",
      "kidnder bueno", "kinder bueno", "cote dor baton",
      "pot cara", "biscuit cream",
      "sucette corazon",
      "arlequin fizz", "candy fizz", "candy", "happy cola",
      "fraizibus", "lutti", "guimau", "schroumpf",
      "tubo oeil", "skdittles", "sachet sour", "bubble gum foot",
      "hwdd style", "hwd blancheur", "bouteillecola",
      "madrs", "mars uvc", "ours or",
      "arlequin", "fraizibus",
      "smarties", "trolli", "dent dracula", "oursons teddy",
      "m ms"], "SUCR_BONBON"),
    (["madeleine", "palmier", "financier", "cookie",
      "biscuit petit beurre", "gateau sec",
      "biscuit the", "sable biscuit",
      "lu barquette", "barquette chocolat",
      "bisc roul", "metro chef bisc",
      "tartelette apero", "tartelette fin",
      "pidy"], "SUCR_BISC"),
    (["gateau moelleux", "cake sale", "quatre quarts",
      "quatre quart", "brownie", "moelleux chocolat", "far breton",
      "barre marbree", "rochambeau",
      "cake choco", "nonnette", "moell coeur caramel",
      "sachet gr mad", "sachet mad"], "SUCR_GATEAU"),
    (["viennoiserie", "croissant boulangerie",
      "pain chocolat frais", "pain raisin"], "SUCR_VIEN"),

    # ── Produits frais — poissons et fruits de mer ────────────────────────────
    (["oeuf", "oeufs plein air", "oeufs bio",
      "oeufs calibre"], "FRAIS_OEUF"),
    (["gambas", "langouste", "homard", "langoustine",
      "crevette fraiche", "crevette rose", "crev deco",
      "crevette", "queue crev"], "FRAIS_CRUST"),
    (["moule", "huitre", "coquille saint jacques",
      "palourde", "praire", "coque", "bigorneau",
      "jacq sc", "st jacq"], "FRAIS_COQUIL"),
    (["saumon frais", "cabillaud frais", "thon frais",
      "daurade fraiche", "daurade royale", "bar frais", "lieu noir",
      "dorade fraiche", "merlan frais", "filet poisson frais",
      "truite fraiche", "sole fraiche", "rouget frais",
      "lotte fraiche", "saumon fume", "pave saumon",
      "dicentrarchus", "flt saumon", "sf ecosse",
      # TAIYAT — poissons import africain/asiatique
      "chinchard", "courbine", "nanka", "malangua",
      "tilapia", "poisson chat", "clarias",
      "baracouda", "sphyraena",
      "empereur", "lethrinus", "ombrine", "micropogonias",
      "eiglefin", "melanogrammus", "pangasius",
      "stockfish", "morue ambassade", "colin sale",
      "maquereau", "scomber",
      "thon garba", "euthynnus", "thon en darne",
      "hareng frais", "sardine frais",
      "scorpene", "mulet", "capitaine"], "FRAIS_POISSON"),

    # ── Produits frais — viandes ──────────────────────────────────────────────
    (["poulet entier", "poulet decoupes", "cuisse poulet",
      "blanc poulet", "aile poulet", "escalope dinde",
      "filet dinde", "magret canard", "cuisse canard",
      "pintade", "faisan", "caille", "dinde entiere",
      "chapon", "volaille",
      "tender crunch", "tenders crunchy", "wings plt", "wing plt",
      "nuggets", "cordon bleu",
      "nem poulet", "nem porc",
      "poule or", "mini bt berger",
      # TAIYAT — volaille import
      "poule doux", "poule fumee", "poule pluvera",
      "exeter poulet", "zwan poulet",
      "corned beef"], "FRAIS_VOLAILLE"),
    (["boeuf", "steak", "entrecote", "faux filet",
      "cote boeuf", "rumsteak", "bavette", "filet boeuf",
      "tournedos", "rosbif", "hampe", "onglet",
      "joue boeuf", "queue boeuf", "paleron", "gite",
      "plat cote", "bourguignon", "hache", "basse cote",
      "queue bf", "vde bourg vbf", "vde bourg",
      "jumeau vbf", "judmeau vbf", "boule macreuse",
      "coeur rtk", "roti marine charolais", "coeur tt", "coeur vbf",
      "sh oblon"], "FRAIS_BOEUF"),
    (["cote porc", "roti porc", "filet porc", "echine porc",
      "gorge porc", "palette porc", "jarret porc",
      "travers porc", "poitrine porc",
      "pied porc", "jarreton porc", "saute porc",
      "jarret s os"], "FRAIS_PORC"),
    (["agneau", "cote agneau", "gigot", "epaule agneau",
      "selle agneau", "veau", "escalope veau",
      "cote veau", "roti veau", "chevreau", "cabri"], "FRAIS_AGNEAU"),
    (["traiteur frais", "quiche fraiche", "feuillete frais",
      "salade composee fraiche", "plat traiteur",
      "wrap frais"], "FRAIS_TRAIT"),

    # ── Boulangerie ──────────────────────────────────────────────────────────
    (["brioche tranch", "brioche fili",
      "brioche nature", "pain briche",
      "brioch bagel", "brioch", "bagel",
      "viennoises fendues", "viennoise fendue"], "BOUL_BRIOCHE"),
    (["croissant boul", "pain chocolat boul",
      "chausson pomme", "pain raisin boul"], "BOUL_VIEN"),
    (["pain", "baguette", "tradition", "ficelle",
      "epi pain", "pain campagne", "pain complet",
      "pain cereale", "pain mie", "mie complet", "fougasse",
      "tranche doree", "mie nature", "pain mie nature",
      "ciabatta", "pita pain", "naan",
      "toast nature", "toast metro chef", "toasti"], "BOUL_PAIN"),

    # ── Fruits & Légumes (aromates avant salade, salade avant légumes) ────────
    (["persil frais", "coriandre fraiche", "basilic frais",
      "menthe fraiche", "ciboulette fraiche", "estragon frais",
      "aneth frais", "thym frais", "herbes fraiches",
      "bouquet garni frais",
      "coriandre sachet", "gingembre sachet",
      "oseille", "persil plat",
      "menthe douce", "ciboulette frai",
      # TAIYAT — aromates frais
      "gingembre frais", "gingembre chine", "gingembre cameroun",
      "ail chine", "ails chine", "ail frais",
      "piment frais", "piment mexique"], "FL_AROMATE"),
    (["salade verte", "frisee", "mesclun", "endive",
      "laitue", "romaine", "mache", "roquette",
      "pousses", "iceberg", "baby carrot"], "FL_SALADE"),
    (["tomate fraiche", "carotte", "courgette",
      "aubergine", "poivron frais", "oignon",
      "poireau", "celeri", "fenouil",
      "champignon frais", "asperge fraiche",
      "brocoli frais", "chou frais", "bette",
      "navet frais", "radis", "concombre",
      "courge", "potiron", "patate douce",
      "pomme terre", "legume frais",
      "epinard frais", "artichaut frais",
      "haricot vert frais", "petits pois frais",
      "mais frais", "oignon blanc", "person",
      "carottes bio",
      "tom rde", "tom grap", "tom cerise", "tom coeur",
      "oig jne", "oig rge", "oig blanc",
      "pdt", "carot", "courg", "auberg",
      "poiv rge", "poiv vert", "poiv jne",
      "concom", "salade bat", "laitue",
      "mchef", "gbox", "dmlt",
      "oig rouge", "oig jne", "oig blanc",
      "oig doux", "pddt", "chou rouge",
      "ban sachet", "ail frais"], "FL_LEGUME"),
    (["pomme", "poire", "orange", "banane", "kiwi",
      "mangue", "ananas", "fraise", "cerise",
      "peche", "abricot", "prune", "raisin",
      "nectarine", "figue fraiche", "grenade",
      "fruit frais", "agrume", "citron", "citr vert",
      "pamplemousse", "melon", "pasteque",
      "litchi", "papaye", "fruit exotique",
      "fruit tropical"], "FL_FRUIT"),

    # ── Produits du Monde ────────────────────────────────────────────────────
    (["halal"], "MONDE_HALAL"),
    (["sauce soja", "sauce oyster", "sauce hoisin",
      "mirin", "sake cuisine", "nouille asiatique",
      "riz gluant", "tofu", "tempeh", "kimchi",
      "miso", "ramen", "udon", "wonton",
      "wok", "huile sesame asie", "vinaigre riz",
      "gochujang", "wasabi", "nori",
      # TAIYAT — nouilles asiatiques
      "yumyum", "yum yum", "nouille thai", "nouille thailand",
      "the fitne", "fitne jaune",
      "tamarin pate", "red dragon"], "MONDE_ASIE"),
    (["couscous maghreb", "houmous", "tahin",
      "harissa", "ras hanout", "semoule fine orient",
      "marocain", "tunisien", "algerien",
      "libanais", "turk produit",
      "zaatar", "sumac epice"], "MONDE_ORIENT"),
    (["tortilla mais", "nachos", "salsa",
      "guacamole", "haricot noir mexicain",
      "chili tex mex", "jalapeno",
      "tabasco", "mexicain prod",
      "bresilien prod"], "MONDE_AMERIQUE"),
    (["ndole", "plantain", "manioc", "gombo",
      "egusi", "farine manioc", "attieke",
      "foufou", "soumbala", "africain prod",
      "cameroun prod", "farine sorgho",
      "mil sorgho", "niebe africain",
      "pate arachide",
      # TAIYAT — produits africains
      "foumboa", "foumbois",
      "bitekuteku", "bitekutek", "amarante",
      "placali", "chikwangue",
      "safou", "kaolin",
      "water fufu", "poundo",
      "yams", "macabo", "taro",
      "pois angole", "pois vaal",
      "haricots cornilles", "niebe",
      "noix kola", "noix petit kola",
      "bissap", "fleur bissap",
      "begue gingembre", "bouillon begue"], "MONDE_AFRIQUE"),

    # ── Snacking ─────────────────────────────────────────────────────────────
    (["chips", "pop corn", "popcorn", "pringles", "soufflet aperitif",
      "tortilla chips", "cracotte",
      "monster munch", "curly", "3d bugles",
      "pringles", "lays", "lay's", "lay s",
      "crispers", "vico", "belin",
      "lady s", "lady's barbecue", "lady's l'ancienne"], "SNACK_CHIPS"),
    (["noix cajou", "amande grille", "pistache grille",
      "noix macadamia", "noix pecan", "noix melange",
      "cacahuete", "graine tournesol", "mix fruit sec",
      "abricot sec", "datte seche", "figue seche",
      "raisin sec", "cranberry seche",
      "prune seche", "fruit oleagineux",
      "barre mgv", "barre cereal", "barre chocolat",
      "graines chia", "cacahuet", "cadcahuet",
      # TAIYAT — arachides / fruits secs
      "arachide emondee", "arachide grillee", "arachide fraiche",
      "arachide boule", "arachides", "arachide"], "SNACK_FRUIT_SEC"),
    (["crackers apero", "tartelette apero",
      "mini bouchee", "feuillete apero",
      "biscuit sale apero", "cheese cracker",
      "palet breton", "palet beurre", "biscuit palet",
      "gressin", "feuille brick",
      # TAIYAT — biscuits import
      "biscuit begue", "sweet biscuit", "sweet biscuit gem",
      "coco caramelise", "nougat",
      "gem biscuit"], "SNACK_BISCUIT"),

    # ── Hygiène & Entretien ───────────────────────────────────────────────────
    (["savon main", "gel douche", "shampooing",
      "deodorant", "dentifrice", "coton tige",
      "rasoir jetable", "hyg corps",
      "gel hydro", "evolu gel", "savona gel",
      "gel mains", "gel antibact"], "HYG_CORPS"),
    (["sopalin", "papier toilette", "essuie tout",
      "mouchoir papier", "serviette papier",
      "kleenex", "ouate", "toil jumbo", "p toil",
      "ph jumbo", "ph 2pli", "ph recyc", "mpro ph"], "HYG_PAPIER"),
    (["lessive", "linge liquide", "tablette lessive",
      "adoucissant linge", "assouplissant", "assoupliss",
      "assoupliss linge", "mpro less liq",
      "ariel pro lessiv", "ariel pro"], "ENTR_LESSIVE"),
    (["javel", "desinfectant multi", "nettoyant wc",
      "nettoyant cuisine", "spray nettoyant",
      "produit nettoyage", "detartrant",
      "nett mu", "nett ms", "netyant", "decap four",
      "gel wc", "acide chlorhydrique",
      "degraissant", "degrais desinf", "lave vitres", "desodo",
      "creme lavante", "recur", "raid aero",
      "savon mousse", "dist savon",
      "wcnet", "wc net", "bloc ocean", "bloc wc",
      "acto cafard", "repulsif", "vanish gold",
      "detach", "acide chlorhyd"], "ENTR_NETTOY"),
    (["liquide vaisselle", "tablette lave vaisselle",
      "sel lave vaisselle", "detergent vaisselle",
      "rinçage vaisselle", "liq vaiss", "lv main"], "ENTR_VAISS"),

    # ── Consommables Professionnels ───────────────────────────────────────────
    (["film etirable", "film alimentaire",
      "papier cuisson", "papier sulfurise",
      "film alu", "bobine", "alu 300", "mpro alu",
      "mpro film alimenta", "ardo alu", "aro alu", "bodbine"], "PRO_FILM"),
    (["gant latex", "gant nitrile", "gant jetable",
      "masque jetable", "toque jetable", "masque 3 pli", "masque pli",
      "charlotte jetable", "pantalon polyvat",
      "sabot", "tablier", "mapa jersette",
      "charlotte blanc"], "PRO_PROTECT"),
    (["etiquette prix", "etiquette vide",
      "rouleau etiquette", "label autocollant",
      "etiq tracabilite", "bloc vend",
      "rlx 57", "sigma rl",
      "manifold fact", "etiquettes", "colop printer",
      "tampon encreur", "chem carte",
      "blocs vend"], "PRO_ETIQ"),
    (["barquette alu", "barquette plastique",
      "boite plastique", "sac kraft", "sachet emballage",
      "emballage alimentaire", "barquette aluminium",
      "boite carton", "caissette", "bac alimentaire",
      "cagette plastique", "sac poub", "sac blanc bret",
      "sac poi kraft",
      "pot sauce", "nappe gaufre", "set gaufre", "set gauffre",
      "set satine",
      "set kraft", "burger kraft", "sets xtra",
      "paille pap", "50barq", "barq couv alu",
      "gel chauffe", "noir couv trans",
      "mpro set", "mpro plat oval", "mpro menu pulp",
      "mpro friteuse", "mpro broch bamb",
      "mpro barq alu", "sac papier kraft",
      "set xtra",
      "mpro 25barq", "sac pingouin", "sac boucher",
      "sac caisse pp",
      # TAIYAT — emballages
      "sac bretelle", "sac liasse", "sac rouleau",
      "sac emballage", "sac boucher", "sac pingouin",
      "palette euro"], "PRO_EMBALL"),
    (["fourchette jetable", "couteau jetable",
      "cuillere jetable", "assiette carton",
      "gobelet plastique", "pique bois", "cure dent",
      "verre plastique", "plateau plastique",
      "brochette bois", "gob carton", "gob chaud", "gob car",
      # TAIYAT — jetables
      "piques brochette", "pique brochette",
      "charbon",
      "gob fh", "gob kraft", "gobelet blanc", "gobelet", "flute open",
      "pic noir", "agitateu", "couv pour pot",
      "couteau steak", "ramasse couvert",
      "serv recyc", "serv 1 pli", "serv 2 pli", "serv pli",
      "serv airlaid",
      "lumignon", "lot doseurs", "doseurs bille",
      "mesure alcool", "rafraichisseur vin",
      "verre pied", "mp assiette", "mpd assiette",
      "mpd saladier", "essoreur", "poubelle pedale",
      "pot sauce", "couv pour pot",
      "serv 2p", "boule inox",
      "tampon epong", "bte noir couv",
      "seau champagne",
      "mp bloc mh", "mp bac gastro",
      "bac gastro", "lot couteau", "fourch table",
      "manche bois", "bol prepa",
      "mp lot", "mp brosse", "mp manche",
      "mp frottoir", "mp distrib", "mp poche",
      "mp ass plate", "mp saladier",
      "mpro lavette", "mpro toque", "mpro gob",
      "mpro lave main", "mpro vap", "mpro coupelle",
      "mpd plat", "mpdro plat",
      "mpro nett sol", "mpro deboucheur",
      "nett ultra degr", "decapant four", "diablotin",
      "bomb spray", "balai synth", "mops micro",
      "pelle balayette", "pulvo", "serp gaufr",
      "jex pro decapant",
      "seau laveur", "seau blanc couv",
      "seau universel",
      "packetiqueteuse",
      "broch bambo", "broch japon", "brochette lasso",
      "bac rect", "gastro ht", "verrine",
      "gob rouge", "gob fb", "gob papier",
      "serv doubl", "cuillere bois", "tablearo",
      "pot sauc", "spatule", "spatules",
      "mpro spatule",
      "cuillere table", "cuilleres table"], "PRO_JETABLE"),

    # ── Catch-all entretien (patterns MPRO/ARO nettoyage) ────────────────
    (["mpro less", "aro essui", "dedsodo",
      "canard wc", "acto appat", "appat blonde"], "ENTR_NETTOY"),
]


# Mots-clés qui indiquent un produit non-alimentaire (nettoyant, pro, hygiène).
# Si présents, les keywords alimentaires (fruit, legume) sont inhibés.
_NON_FOOD_MARKERS: frozenset[str] = frozenset({
    "nett", "desodo", "javel", "decap", "degraiss",
    "bact", "chlor", "desinfect", "detart", "recur",
    "lave vitre", "gel wc", "savon", "creme lavante",
    "dist savon", "raid", "solijavel", "boldair",
    "tampon", "epong", "bobine", "film alu", "serv 2p",
    "set gaufre", "set kraft", "set satine", "sac poub", "gob carton",
    "gob chaud", "gob fh", "gob kraft", "gobelet", "assiette", "couteau",
    "boule inox", "agitateu", "pic noir", "lumignon",
    "nappe", "bloc mh", "bloc vend", "masque 3", "masque pli",
    "planch", "bac gastro", "lot 24 couteau",
    "essoreur", "poubelle", "doseurs", "rafraichiss",
    "mpd saladier", "mpd assiette", "mp assiette",
    "seau champagne", "verre pied", "mesure alcool",
    "acto cafard", "acto appat", "repulsif", "vanish", "detach",
    "gel chauffe", "50barq",
    "mpro lavette", "mpro toque", "mpro gob",
    "mpro lave main", "mpro vap", "mpro coupelle",
    "mp lot", "mp brosse", "mp manche", "mp frottoir",
    "mp distrib", "mp poche", "mp ass plate",
    "seau laveur", "seau universel", "seau blanc",
    "canard wc", "dedsodo",
    "balai synth", "serp gaufr",
    "mpro nett", "mpro deboucheur", "mpro spatule",
    "pringles",  # snack, pas légume (inhibe FL_LEGUME sur "oignon")
})

# Catégories alimentaires qui produisent des faux positifs sur des non-alimentaires
_FOOD_ONLY_CATEGORIES: frozenset[str] = frozenset({
    "FL_FRUIT", "FL_LEGUME", "FL_AROMATE", "FL_SALADE",
    "FRAIS_BOEUF", "FRAIS_PORC", "FRAIS_VOLAILLE", "FRAIS_AGNEAU",
    "FRAIS_POISSON", "FRAIS_CRUST", "FRAIS_COQUIL",
    "BOIS_THE", "BOIS_JUS", "BOIS_SIROP",
    "EPIC_SEMOULE", "EPIC_RIZ",
    "SURG_GLACE", "SURG_LEGUME", "SURG_VIANDE",
})


def lookup_correction_history(designation_norm: str) -> str | None:
    """Layer 0 : cherche dans l'historique des corrections manuelles.

    Si une désignation identique a déjà été corrigée par un opérateur,
    retourne la catégorie choisie avec une confiance élevée.
    Non-bloquant : retourne None si DB inaccessible ou pas de match.
    """
    try:
        from sqlalchemy import select as _sel, desc
        from app.models.catalogue.etl_correction_history import EtlCorrectionHistory

        # Import synchrone léger — ce module est appelé dans un contexte sync
        # La query sera faite en async dans _resolve_categorie_code (etl_import_service)
        # Ici on expose juste la logique, l'appel sera fait depuis le caller async
        return None  # Placeholder — l'appel réel est fait dans etl_import_service
    except Exception:
        return None


def classify_categorie_code(designation_norm: str) -> str:
    """Retourne le code de catégorie alimentaire pour une désignation normalisée.

    Stratégie :
      0. Historique corrections manuelles (layer 0, via caller async)
      1. Pré-détection non-alimentaire (mots-clés nettoyant/pro/hygiène)
      2. Règles ordonnées (premier match gagne)
      3. Si un produit est non-alimentaire, les catégories food-only sont inhibées

    Args:
        designation_norm: Désignation normalisée (NFD→ASCII, lowercase, stop words).

    Returns:
        Code catégorie UPPER_CASE. Défaut : 'AUTRE'.
    """
    if not designation_norm:
        return _FALLBACK_CODE
    text = designation_norm.lower()

    # Pré-détection : le produit contient-il des marqueurs non-alimentaires ?
    is_non_food = any(marker in text for marker in _NON_FOOD_MARKERS)

    for keywords, code in _RULES:
        if any(kw in text for kw in keywords):
            # Si non-food détecté, inhiber les catégories alimentaires
            if is_non_food and code in _FOOD_ONLY_CATEGORIES:
                continue
            return code
    return _FALLBACK_CODE


def classify_by_knn(
    designation_norm: str,
    labelled: list[tuple[str, str]],
    seuil: float = _KNN_SEUIL,
) -> str:
    """KNN k=1 : propage la catégorie du voisin le plus proche (Jaro-Winkler).

    Utilisé en couche 2 quand classify_categorie_code() retourne AUTRE.
    Le voisin est cherché dans `labelled`, liste de (designation_norm, code)
    construite dynamiquement pendant l'import depuis les produits déjà classifiés.

    Args:
        designation_norm: Désignation normalisée du produit entrant.
        labelled: Paires (designation_norm, code) des produits déjà classifiés
            (code ≠ AUTRE). Peut être vide.
        seuil: Score Jaro-Winkler minimum pour propager. Défaut : _KNN_SEUIL=0.80.

    Returns:
        Code hérité du voisin si score ≥ seuil, sinon AUTRE.
    """
    if not designation_norm or not labelled:
        return _FALLBACK_CODE
    text = designation_norm.lower()
    best_score = 0.0
    best_code = _FALLBACK_CODE
    for cand_norm, code in labelled:
        score = compute_similarity(text, cand_norm)
        if score > best_score:
            best_score = score
            best_code = code
            if best_score >= 1.0:
                break
    return best_code if best_score >= seuil else _FALLBACK_CODE


def classify_by_knn_top_n(
    designation_norm: str,
    labelled: list[tuple[str, str]],
    seuil: float = 0.60,
    n: int = 3,
) -> list[dict]:
    """Top-N catégories par KNN Jaro-Winkler.

    Returns:
        [{code, score}, ...] trié par score desc, filtré par seuil.
    """
    if not designation_norm or not labelled:
        return []
    text = designation_norm.lower()
    scored: dict[str, float] = {}
    for cand_norm, code in labelled:
        score = compute_similarity(text, cand_norm)
        if score >= seuil:
            if code not in scored or score > scored[code]:
                scored[code] = score
    results = [{"code": c, "score": round(s, 3)} for c, s in scored.items()]
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:n]
