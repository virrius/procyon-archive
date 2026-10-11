"""Английские данные генератора имён — двойник names.py, логика остаётся там.

Сеттинговые имена, фамилии и прозвища корника — в написании английской книги (Scum and
Villainy, стр. 62); придуманные — латиницей в том же духе. Мировая база — в принятом для
культуры латинском написании: родные диакритики латинских алфавитов сохраняются (José,
Dvořák, Björn), остальное — стандартная романизация без тонов и долгот (Zhang, Saito,
Nguyen). FAMILY_F — женские формы фамилий там, где культура их требует.
"""

__all__ = [
    "SETTING_FIRST", "SETTING_FAMILY", "ALIAS", "XENO", "COUNTRIES", "GROUPS", "FEMALE",
    "FAMILY_F",
]


SETTING_FIRST = [
    "Abra", "Ignor", "Aria", "Victor", "Wyndam", "Gaius", "Garm", "Gurney", "Garrus",
    "Greeg", "Del", "Jaana", "Jango", "Genera", "Jerec", "Jet", "Duncan", "Zokar",
    "Yola", "Kai", "Kahlee", "Kalo", "Kasumi", "Quinton", "Chendra", "Kirk", "Kit",
    "Cord", "Xavier", "Lando", "Leto", "Liara", "Lotus", "Mevakor", "Mill", "Mino",
    "Miranda", "Mordin", "Naimon", "Needa", "Orrin", "Poe", "Paul", "Potak", "Praxis",
    "Rey", "Rocco", "Zaeed", "Saldeed", "Samara", "Saren", "Seklor", "Spike", "Thane",
    "Oola", "Faykan", "Finn", "Fox", "Faye", "Hirak", "Han", "Hondo", "Ed", "Entex",
    "Espa", "Jung", "Yast", "Axin", "Arden", "Baris", "Brekk", "Valdo", "Vane", "Vigo",
    "Garro", "Gell", "Darv", "Dane", "Jax", "Erro", "Zayan", "Zevra", "Ista", "Irdo",
    "Kyra", "Kalek", "Karn", "Ketta", "Kirn", "Corvo", "Kress", "Lada", "Laxo", "Lenn",
    "Lorca", "Madge", "Merro", "Milka", "Naro", "Nate", "Nisa", "Ovra", "Audrey",
    "Orso", "Pallo", "Perra", "Pierce", "Ravn", "Rezo", "Rinn", "Roska", "Savren",
    "Seska", "Soren", "Stren", "Tyra", "Tarko", "Tella", "Fasco", "Fenn", "Hado",
    "Helka", "Cerra", "Shayla", "Shedd", "Eira", "Ekko", "Yurn", "Yass",
]


SETTING_FAMILY = [
    "Acon", "Bartok", "Black", "Brell", "Valorum", "Veers", "Wolffe", "Vosa", "Wu",
    "Gyle", "Gallia", "Gree", "Dyson", "Jor", "Jusik", "Drake", "Doona", "Yoneyama",
    "Zan", "Zer", "Ivanov", "Impera", "Indigo", "Intal", "Kasur", "Kedra", "Kymnal",
    "Clovis", "Kor", "Kranax", "Crynyd", "Kritus", "Kromyl", "Quag", "Curia", "Lana",
    "Livia", "Luo", "Mahat", "Marak", "Nagan", "Natoth", "Neumann", "Nur", "Ortcutt",
    "Pava", "Pim", "Ryle", "Ramus", "Wren", "Rudra", "Suzuka", "Tann", "Tarkin", "Tel",
    "Tilad", "Thorn", "Ulmak", "Ursis", "Farr", "Feris", "Hex", "Hill", "Hawking",
    "Sprek", "Shrike", "Evazan", "Emari", "Endua", "Apple", "Yularen", "Yueh", "Ardax",
    "Astven", "Bellar", "Brendis", "Veylan", "Verkan", "Villar", "Grax", "Grimo",
    "Delvar", "Dorven", "Drask", "Zorran", "Innis", "Yorval", "Karris", "Kassel",
    "Kellar", "Craven", "Krendo", "Lavris", "Lenvar", "Lorhan", "Marven", "Mersal",
    "Naldo", "Nissar", "Nordvik", "Olwen", "Ormak", "Pellar", "Price", "Ravell",
    "Reven", "Risto", "Sarran", "Sever", "Skarn", "Sollar", "Tandel", "Tassel",
    "Torven", "Ullo", "Ursal", "Faer", "Fenrick", "Hallan", "Hemmet", "Zircon",
    "Shoran", "Eddar", "Elven", "Yumar", "Yarven",
]


ALIAS = [
    "Agony", "Apex", "Ace", "Athena", "Badger", "Bingo", "Lasher", "Razor", "Vandal",
    "Dash", "Bolt", "Eight", "Intake", "Helo", "Nails", "Hyper", "Gonzo", "Gargoyle",
    "Zen", "Vapor", "Stinger", "Iron", "Yellow", "Juggler", "Quirk", "Link", "Zenith",
    "Game", "Karma", "Dipper", "Cosmo", "Snaps", "Legend", "Mooch", "Elbows", "Junior",
    "Zipper", "Hammer", "Carrot", "Cash", "Nemesis", "Under", "Nova", "Fireball",
    "Headhunter", "Wraith", "Loco", "Guns", "Iris", "Raider", "X-Ray", "Rash", "Hex",
    "Syndrome", "Juice", "Falcon", "Highball", "Snitch", "Tax", "Tank", "Titan",
    "Brakes", "Phoenix", "Owl", "Flex", "Skulls", "Black", "Devil", "Tread", "Gear",
    "Echo", "Ballast", "Barrel", "Bucket", "Pane", "Nut", "Jack", "Tape", "Crane",
    "Winch", "Hatch", "Crude", "Sawn-Off", "Manifold", "Seal", "Springs", "Whistle",
    "Sling", "Cleaver", "Rattle", "Wick", "Clamp", "Pin", "Awl", "Kingpin", "Splinter",
    "Core", "Dowel", "Rivet", "Sledge", "Hacksaw", "Penny", "Tuppence", "Coupon",
    "Pawn", "Arrears", "Kitty", "Vig", "Nickel", "IOU", "Stake", "Meter", "Yard",
    "Upfront", "Bail", "Markup", "Payoff", "Penalty", "Write-Off", "Eyelid", "Hump",
    "Stutter", "Cough", "Smokey", "Cockeye", "Fist", "Baldy", "Pinky", "Hangnail",
    "Squint", "Soot", "Rasp", "Stoop", "Scar", "Gaptooth", "Milkeye", "Gullet",
    "Shovel", "Patch", "Huckster", "Speedy", "Crack", "Chisel", "Sliver", "Wedge",
    "Paws", "Wetwork", "Tip-Off", "Picks", "Draft", "Fence", "Sit-Down", "Tail",
    "Lookout", "Hood", "Con", "Kite", "Minder", "Cat", "Vacuum", "Gravel", "Nozzle",
    "Eclipse", "Wake", "Comet", "Meteor", "Orbit", "Perigee", "Belt", "Thruster",
    "Dock", "Thrust", "Haze", "Apogee", "Adrift", "Plasma", "Regolith", "Photon",
    "Ecliptic", "Vulture", "Ruff", "Widow", "Boar", "Moray", "Sturgeon", "Piranha",
    "Woodchuck", "Ferret", "Jackal", "Lizard", "Barracuda", "Otter", "Viper", "Tern",
    "Bustard", "Angel", "Pops", "Witch", "Guest", "Heresy", "Patron", "Meek", "Quiet",
    "Pastor", "Psalm", "Saint", "Hush", "Lucky", "Tattle", "Blessed", "Widower",
    "Compadre", "Pilgrim", "Monk", "Fool", "Knave", "Joker", "Trump", "Marriage",
    "Misery", "Pass", "Shuffle", "Faro", "Spades", "Chip", "Sharp", "Bank", "Blizzard",
    "Hail", "Frost", "Rime", "Torrent", "Murk", "Glaze", "Twister", "Drought", "Mire",
    "Squall", "Sunny", "Hooch", "Muffin", "Goulash", "Yeast", "Jelly", "Ration",
    "Pepper", "Brine", "Hardtack", "Vinegar", "Toffee", "Bass", "Pipes", "Klaxon",
    "Fife", "Kettle", "Octave", "Rhubarb", "Piccolo", "Strings", "Tremolo", "Falsetto",
    "Hurdy-Gurdy", "Parapet", "Brass", "Patrol", "Volley", "Phalanx", "Detail",
    "Foxhole", "Stock", "Ricochet", "Salute", "Trench", "Bayonet", "Chicane", "Drift",
    "Skid", "Ring", "Overtake", "Pitstop", "Throttle", "Freeze-Frame", "Jumpstart",
    "Finish", "Hairpin", "Twenty", "Niner", "Dozen", "Zero", "First", "Fifth", "Seven",
    "Hundo", "Third", "Thirteen", "Fours", "Crimson", "Whitey", "Umber", "Cobalt",
    "Indigo", "Azure", "Ochre", "Ash", "Slate", "Amber", "Bravo", "Victor", "Golf",
    "Delta", "Kilo", "Lima", "Double-Oh", "Oscar", "Romeo", "Tango", "Foxtrot",
    "Echo-Two", "Uniform",
]


XENO = [
    "Aash'ti", "Ashtrekk", "Vrrekh", "Vish'la", "Ghal-Tu", "Gsherr", "Dzekkt",
    "Dharr-Ssu", "Issarin", "Ix'lo", "Yrru", "Yshant", "Kkal", "Ktorr", "Ktarr",
    "Kshemm", "Lu'veni", "Llash", "Mharo", "Mshett", "Neet", "Nharro", "Ossu", "Oshten",
    "Pharr", "Psell", "Rhush", "Rraikh", "Sselik", "Skharn", "Tchekk", "Tharro", "Ummo",
    "Usshin", "Fsherr", "Fhal", "Khshaa", "Khtenn", "Tsvirr", "Tsshell", "Shemmet",
    "Shkharro", "Shcharr", "Erg'la", "Essho", "Yussh", "Yarro", "Yasshet", "Barum-Og",
    "Vogdal", "Grong", "Durmo", "Zagbar", "Kerum", "Logvar", "Mormo", "Naggur", "Ogbar",
    "Rumtal", "Togmar", "Ubron", "Hurgal", "Shodar", "Aeli'in", "Veolla", "Innale",
    "Yolie", "Kealua", "Lienne", "Mauali", "Niella", "Oalie", "Sienna", "Talue",
    "Uanne", "Eliena", "Eighth-of-Needles", "Second-Seam", "Nest-Ku", "Far-Wedge",
    "Bulwark-Three", "Fang-Seven", "Thread-Twelve", "Bearer-Ro", "First-of-Dust",
    "Fifth-of-Mica", "Net-Sha", "Gazes-Down", "Shade-Eleven", "Choir-Four", "Seam-Nine",
    "Je'Morag", "Iz'Kenne", "Ka'Rattu", "Lo'Sinni", "Na'Hatt", "Or'Valli", "Su'Mmero",
    "Ta'Kessir", "Ur'Mo", "He'Llant", "Aashten", "Azzo", "Vrassh", "Vikkt", "Ghorru",
    "Gsshell", "Dzakkt", "Dhonn", "Izzarro", "Ishtu", "Yokho", "Yshrra", "Kkennu",
    "Ktorkh", "Kshissh", "Lhasso", "Llirro", "Mhenn", "Mshorra", "Nnash", "Nhutto",
    "Ossarr", "Okhshenn", "Phorro", "Pshenn", "Rrokh", "Rhenno", "Ssannet", "Sshorro",
    "Thenno", "Tsharro", "Ukho", "Ushmarr", "Fhenno", "Fshorro", "Khshetto", "Khtarro",
    "Tsshenn", "Tskhorro", "Shkhenno", "Sshorra", "Shchenno", "Ekhsho", "Essharro",
    "Yussho", "Yakhsho", "Yarkhenno", "Barum-Dol", "Vogmar", "Grongur", "Durtal",
    "Zagmo", "Kerumba", "Logtar", "Mormag", "Naggal", "Ogtorn", "Rumgar", "Togbrut",
    "Ubmor", "Hurdal", "Shodmo", "Yurmo", "Aelienne", "Veolle", "Innael", "Yolienna",
    "Kealue", "Liennae", "Maualie", "Niellae", "Oalienne", "Siennae", "Taluenne",
    "Uannelli", "Elienne", "Second-of-Dust", "Nest-Ro", "Far-Seam", "Bulwark-Seven",
    "Fang-Twelve", "Thread-Three", "Bearer-Sha", "First-of-Needles", "Fifth-of-Wedge",
    "Net-Eleven", "Gazes-Up", "Shade-Four", "Choir-Nine", "Seam-Eight", "Je'Rattu",
    "Iz'Morag", "Ka'Sinni", "Lo'Kenne", "Na'Valli", "Or'Hatt", "Su'Kessir", "Ta'Mmero",
    "Ur'Llant", "He'Mo",
]


COUNTRIES: dict[str, dict] = {
    "ru": {
        "label": "Russia",
        "first": [
            "Aglaya", "Akim", "Anfisa", "Arkady", "Boris", "Valentina", "Varvara",
            "Vera", "Vladimir", "Galina", "Gleb", "Grigory", "Danila", "Dmitry",
            "Yevgenia", "Yefim", "Zakhar", "Zoya", "Ignat", "Ilya", "Irina", "Klim",
            "Ksenia", "Larisa", "Lidia", "Lukerya", "Makar", "Maria", "Matvey",
            "Nadezhda", "Nikifor", "Nikolai", "Olga", "Pavel", "Praskovya", "Rodion",
            "Svetlana", "Semyon", "Sergei", "Stepan", "Tamara", "Tikhon", "Ustinya",
            "Fyodor", "Frol", "Yuri", "Yakov", "Yarina",
        ],
        "family": [
            "Aksyonov", "Belyaev", "Vorontsov", "Gagarin", "Dementyev", "Yershov",
            "Zhukov", "Zotov", "Ilyin", "Kirillov", "Kolesov", "Luzhin", "Mazurov",
            "Nekrasov", "Ovchinnikov", "Pankratov", "Prokhorov", "Rogozhin", "Savelyev",
            "Sotnikov", "Tarasov", "Ushakov", "Fomin", "Khabarov", "Chernyak",
            "Shevchuk", "Shcherbakov", "Yurin", "Yakovlev",
        ],
    },
    "us": {
        "label": "America",
        "first": [
            "Abigail", "Ira", "Amanda", "Brian", "Brendan", "Vivian", "Gloria", "Grace",
            "Dana", "Derek", "Jasper", "Joan", "Dylan", "Douglas", "Eden", "Kyle",
            "Kevin", "Clark", "Lauren", "Madeline", "Marvin", "Maeve", "Melissa",
            "Nathan", "Noel", "Oliver", "Patrick", "Priscilla", "Rita", "Rowan",
            "Sidney", "Stella", "Tessa", "Travis", "Wyatt", "Fiona", "Floyd", "Hazel",
            "Chloe", "Chester", "Everett", "Edith", "Elijah", "Emmett",
        ],
        "family": [
            "Barlow", "Bennett", "Brooks", "Ventress", "Grady", "Donaldson", "Draper",
            "Casey", "Caldwell", "Cooper", "Langley", "McTavish", "Mercer", "North",
            "O'Donnell", "Price", "Randall", "Sutherland", "Slater", "Sterling",
            "Thatcher", "Whitmore", "Wade", "Fowler", "Fitzgerald", "Hendricks",
            "Holloway", "Chestnut", "Shelby", "Ashford",
        ],
    },
    "gb": {
        "label": "Britain",
        "first": [
            "Agnes", "Brendan", "Viola", "Grace", "Duncan", "Eden", "Kieran", "Clara",
            "Lloyd", "Maeve", "Niall", "Oliver", "Patrick", "Rowan", "Sorcha", "Tessa",
            "Finlay", "Hamish", "Aidan", "Emmett",
        ],
        "family": [
            "Abercrombie", "Barlow", "Ventress", "Grady", "Donaldson", "Cunningham",
            "Maguire", "McTavish", "O'Donnell", "Price", "Slater", "Thatcher", "Wade",
            "Fitzgerald", "Hendricks", "Shelby",
        ],
    },
    "fr": {
        "label": "France",
        "first": [
            "Adeline", "Amélie", "Anselme", "Baptiste", "Benoît", "Virginie", "Gaspard",
            "Delphine", "Geneviève", "Julien", "Yvette", "Clément", "Colette",
            "Laurent", "Lucien", "Madeleine", "Margot", "Mathieu", "Mireille",
            "Norbert", "Odile", "Pascal", "Rémi", "Rosalie", "Séverine", "Sylvie",
            "Thibault", "Urbain", "Fabien", "Florian", "Chantal", "Éloïse", "Émile",
            "Huguette",
        ],
        "family": [
            "Hardouin", "Blanchard", "Vernier", "Garnier", "Dufour", "Carrier",
            "Lacroix", "Lambert", "Leclerc", "Maréchal", "Morel", "Pelletier", "Picard",
            "Roux", "Thévenin", "Fontaine", "Charbonneau", "Hervé",
        ],
    },
    "de": {
        "label": "Germany",
        "first": [
            "Anneke", "Bastian", "Willem", "Gerda", "Dirk", "Johannes", "Klaus",
            "Liselotte", "Matthias", "Otto", "Rutger", "Svenja", "Till", "Ursula",
            "Friedrich", "Heike", "Jürgen", "Jan",
        ],
        "family": [
            "Baumgartner", "van der Berg", "Weber", "Groot", "Dietrich", "Köhler",
            "Kranz", "Lemke", "Müller", "Nissen", "Reimers", "Scholten", "Vogel",
            "Schwarz",
        ],
    },
    "it": {
        "label": "Italy",
        "first": [
            "Alice", "Benedetto", "Vittorio", "Gianna", "Dino", "Cosimo", "Letizia",
            "Marcello", "Nina", "Orso", "Pietro", "Rosalba", "Severino", "Tonio",
            "Fiore", "Cesare",
        ],
        "family": [
            "Allegri", "Bertolini", "Viani", "Galliano", "Zanetti", "Caldera",
            "Lazzaro", "Mazzarini", "Orsini", "Pellegrini", "Ricci", "Sartore",
            "Toscani", "Ferreira",
        ],
    },
    "gr": {
        "label": "Greece",
        "first": [
            "Alexios", "Vasiliki", "Glykeria", "Dimitra", "Zoi", "Ioannis", "Xenia",
            "Leonidas", "Myrto", "Nikos", "Panagiota", "Stavros", "Fotini", "Christos",
        ],
        "family": [
            "Apostolou", "Vardakis", "Georgiadis", "Doukas", "Kyriakos", "Lambros",
            "Nikolaou", "Papadakis", "Sideris", "Xanthopoulos",
        ],
    },
    "pl": {
        "label": "Poland & Czechia",
        "first": [
            "Agnieszka", "Bogusław", "Václav", "Grzegorz", "Danuta", "Ewa", "Zdena",
            "Jiří", "Kazimierz", "Libuše", "Mirosław", "Oldřich", "Radek", "Stanisław",
            "Tadeusz", "Hanka", "Józef", "Jadwiga",
        ],
        "family": [
            "Wróbel", "Dvořák", "Zaręba", "Kamiński", "Kováč", "Kubica", "Mazowiecki",
            "Nowak", "Pełka", "Sikora", "Tesař", "Hrudoš", "Červenka", "Jastrzębski",
        ],
    },
    "no": {
        "label": "Scandinavia",
        "first": [
            "Aivars", "Astrid", "Birutė", "Björn", "Gediminas", "Gunnar", "Dagny",
            "Daina", "Yngve", "Jonas", "Jorunn", "Knut", "Laima", "Lovisa", "Magnus",
            "Mantas", "Nils", "Rasa", "Sigrid", "Sven", "Solveig", "Torvald", "Uldis",
            "Ulla", "Freja", "Helga", "Eglė", "Eirik", "Erling",
        ],
        "family": [
            "Aalto", "Balodis", "Bergman", "Vītols", "Gudaitis", "Dahl", "Johansen",
            "Kalniņš", "Kristiansen", "Lazdiņš", "Lindgren", "Magnusson", "Norberg",
            "Norkus", "Ozols", "Söderblom", "Tormundsen", "Holm", "Eriksson",
        ],
    },
    "in": {
        "label": "India",
        "first": [
            "Ajay", "Amrita", "Anjali", "Ashmita", "Bikash", "Viran", "Deepak", "Dhara",
            "Ishan", "Kavya", "Kumari", "Lakshmi", "Madhuri", "Neelam", "Nirmala",
            "Prabin", "Pritam", "Ravi", "Rohan", "Sunita", "Sunil", "Tara", "Ujjwal",
            "Harshad", "Chamara", "Chitra",
        ],
        "family": [
            "Adhikari", "Iyer", "Bandara", "Bhatia", "Gupta", "Gurung", "Dhawan",
            "Jayawardene", "Kapoor", "Magar", "Mehta", "Nair", "Perera", "Rai",
            "Ranaut", "Singhal", "Thakur", "Thapa", "Fernando", "Chaudhary", "Sharma",
            "Shrestha",
        ],
    },
    "cn": {
        "label": "China",
        "first": [
            "Wei", "Ganhua", "Deming", "Rulan", "Liu", "Meiling", "Peng", "Xiaoyan",
            "Tao", "Han'er", "Jin", "Zhen", "Shuiyin", "Yunfei",
        ],
        "family": [
            "Wang", "Deng", "Li", "Lin", "Liu", "Xu", "Tang", "Huang", "Tsang", "Zhang",
            "Zhao", "Yang",
        ],
    },
    "jp": {
        "label": "Japan",
        "first": [
            "Ayumi", "Daisuke", "Izumi", "Keiko", "Mitsuru", "Natsumi", "Ren", "Satomi",
            "Takeshi", "Haruna", "Tsuyoshi", "Yukio", "Yasuo",
        ],
        "family": [
            "Inoue", "Kobayashi", "Mori", "Nakamura", "Okada", "Saito", "Shoji",
            "Takagi", "Fujiwara", "Hattori", "Yamashita", "Yoneyama",
        ],
    },
    "kr": {
        "label": "Korea",
        "first": [
            "Ji-woo", "Young-hee", "Min-ho", "Nam-gyu", "Seon-mi", "Tae-hyun", "Ha-eun",
            "Chang-wook", "Yu-na",
        ],
        "family": [
            "Ahn", "Jeong", "Kang", "Kim", "Lee", "Park", "Seo", "Han", "Cho", "Yoon",
        ],
    },
    "sea": {
        "label": "Southeast Asia",
        "first": [
            "Anh", "Boonmee", "Dang", "Quang", "Lan", "Ngoc", "Pranee", "Somchai",
            "Thao", "Chayanan", "Yui", "Ade", "Bambang", "Darma", "Indra", "Kusuma",
            "Lestari", "Nurul", "Putra", "Siti", "Wayan", "Hanif", "Yusman", "Amihan",
            "Bai", "Dalisay", "Imang", "Lucinda", "Mabini", "Narra", "Reymon",
            "Sampaguita", "Tala",
        ],
        "family": [
            "Bunnag", "Van", "Dang", "Le", "Nguyen", "Panya", "Rattanakorn", "Tran",
            "Pham", "Hoang", "Abdullah", "Wijaya", "Gunawan", "Ibrahim", "Kusuma",
            "Lestari", "Prabowo", "Santoso", "Tan", "Hakim", "Agbayani", "Bautista",
            "Delgado-Cruz", "Cabrera", "Laksamana", "Magsaysay", "Pangilinan",
            "Remigio", "Salonga", "Tiamson",
        ],
    },
    "tr": {
        "label": "Turkey",
        "first": [
            "Azra", "Bekir", "Gülsen", "Demir", "Emre", "İlkay", "Kemal", "Lale",
            "Murat", "Nesrin", "Ozan", "Selim", "Tuncay", "Fatma", "Yasin",
        ],
        "family": [
            "Aydın", "Bektaş", "Demirel", "Ercan", "Kemal", "Öztürk", "Polat", "Soylu",
            "Taşkın", "Erdoğan", "Yalçın", "Yaşar",
        ],
    },
    "ar": {
        "label": "Arab World",
        "first": [
            "Aisha", "Bahir", "Jamila", "Zahra", "Ibrahim", "Karima", "Layla",
            "Mansour", "Nasim", "Rashid", "Sabin", "Tariq", "Farida", "Habiba", "Yusra",
            "Yasir", "Anoush", "Behrouz", "Goli", "Dariush", "Zahir", "Qadir", "Mehri",
            "Nader", "Parvin", "Rostam", "Soheila", "Fereydun", "Hevron", "Shirin",
        ],
        "family": [
            "Ammar", "Bishara", "Jaber", "Zahrani", "Ibrahimi", "Kaddouri", "Mansour",
            "Najafi", "Rahimi", "Safar", "Tahir", "Haddad", "Sharif", "Yusuf", "Ansari",
            "Beheshti", "Golestani", "Dehghani", "Zahedi", "Kermani", "Mohammadi",
            "Nemati", "Rasouli", "Shirazi",
        ],
    },
    "il": {
        "label": "Israel",
        "first": [
            "Avital", "Baruch", "Gilad", "Dafna", "Yoav", "Miriam", "Naomi", "Rachel",
            "Simcha", "Tamar", "Uriah", "Shlomo",
        ],
        "family": [
            "Avraami", "Barzilai", "Goldberg", "Dyachkov", "Katz", "Levi", "Mizrahi",
            "Regev", "Finkel", "Shapira",
        ],
    },
    "cauc": {
        "label": "Caucasus",
        "first": [
            "Ashot", "Vazgen", "Guram", "Darejan", "Zaur", "Ketevan", "Lali", "Nino",
            "Ruben", "Siranush", "Tamaz", "Eldar",
        ],
        "family": [
            "Abashidze", "Babayan", "Gogua", "Dadiani", "Ghazaryan", "Mgeladze",
            "Hovhannisyan", "Saakadze", "Ter-Petrosyan", "Chkheidze",
        ],
    },
    "turk": {
        "label": "Central Asia",
        "first": [
            "Ainur", "Batyr", "Gulmira", "Daniyar", "Zhanat", "Kairat", "Madina",
            "Nurlan", "Saule", "Temirlan", "Ulzhan", "Chinara",
        ],
        "family": [
            "Abdirov", "Baiseitov", "Dauletov", "Zhumabayev", "Iskakov", "Karimov",
            "Murzayev", "Nurbekov", "Sagyndykov", "Tulegenov",
        ],
    },
    "wafr": {
        "label": "West Africa",
        "first": [
            "Abiola", "Adjoa", "Dauda", "Ifeoma", "Kofi", "Mansata", "Ngozi", "Obioma",
            "Segun", "Tkakor", "Folake", "Yaw",
        ],
        "family": [
            "Abasi", "Ajayi", "Babangida", "Diallo", "Keita", "Mbeng", "Ndiaye",
            "Okonkwo", "Osei", "Touré",
        ],
    },
    "eafr": {
        "label": "East Africa",
        "first": [
            "Asali", "Baraka", "Juma", "Zaudi", "Kito", "Mosib", "Neema", "Penda",
            "Simba", "Khadija", "Abeba", "Bekele", "Getachew", "Desta", "Yemane",
            "Kerkos", "Meskel", "Selam", "Tesfaye", "Hanna",
        ],
        "family": [
            "Abdalla", "Juma", "Kimani", "Mwangi", "Nnko", "Omari", "Salim", "Ujiru",
            "Hamisi", "Chauke", "Abebe", "Bekele", "Gebre", "Desalegn", "Kassa",
            "Mariam", "Tadesse", "Tesfaye", "Haile", "Yilma",
        ],
    },
    "safr": {
        "label": "Southern Africa",
        "first": [
            "Bongi", "Vivi", "Dlamini", "Zuri", "Kagiso", "Mbali", "Nolwazi", "Sipho",
            "Thando", "Tumelo",
        ],
        "family": [
            "Dlamini", "Zulu", "Kibuka", "Mabasa", "Mbeki", "Nkosi", "Sibanda",
            "Tshabalala", "Hadebe", "Chabalala",
        ],
    },
    "latam": {
        "label": "Latin America",
        "first": [
            "Aurelio", "Benita", "Vicente", "Dulce", "Hilario", "Inés", "Carmen",
            "Lucía", "Manuela", "Mercedes", "Nicolás", "Osorio", "Pilar", "Rafael",
            "Rodrigo", "Sol", "Tiago", "Ximena", "Esteban", "Juliana",
        ],
        "family": [
            "Alarcón", "Barrios", "Vieira", "García", "Delgado", "Cabral", "Cabrera",
            "Méndez", "Navarro", "Ortega", "Pangilinan", "Pinheiro", "Ribeiro",
            "Salonga", "Santos", "Tavares", "Ferreira", "Espinosa",
        ],
    },
    "poly": {
        "label": "Oceania",
        "first": [
            "Apo", "Ika", "Keala", "Kuamu", "Malia", "Moana", "Noelani", "Tane", "Uilu",
            "Hiapo", "Ayasha", "Winona", "Kayenne", "Mato", "Nanuk", "Sitsi", "Tokala",
            "Hiawatha", "Chayton", "Yata",
        ],
        "family": [
            "Anuera", "Kaiulani", "Keahi", "Mahone", "Noa", "Rangihau", "Taiaroa",
            "Tupu", "Fa'anga", "Heke", "Begay", "Wind Horse", "Ghost", "Red Elk",
            "Littlebird", "Bear Ravine", "Nahai", "Darkwater", "Hawkbeak", "Yata",
        ],
    },
}


GROUPS: list[tuple[str, str, tuple[str, ...]]] = [
    ("ru", "Russia", ("ru",)),
    ("us", "America", ("us",)),
    ("gb", "Britain", ("gb",)),
    ("fr", "France", ("fr",)),
    ("eu", "Europe", ("de", "it", "gr", "pl",)),
    ("no", "Scandinavia", ("no",)),
    ("in", "India", ("in",)),
    ("east", "East Asia", ("cn", "jp", "kr", "sea",)),
    ("mideast", "Middle East", ("tr", "ar", "il", "cauc", "turk",)),
    ("africa", "Africa", ("wafr", "eafr", "safr",)),
    ("latam", "Latin America", ("latam",)),
    ("poly", "Oceania", ("poly",)),
]


FEMALE: dict[str, frozenset[str]] = {
    "setting": frozenset((
        "Aria", "Jaana", "Genera", "Yola", "Kahlee", "Kasumi", "Chendra", "Liara",
        "Lotus", "Miranda", "Samara", "Oola", "Faye", "Espa", "Kyra", "Ketta", "Lada",
        "Milka", "Nisa", "Audrey", "Perra", "Roska", "Seska", "Tyra", "Tella", "Helka",
        "Cerra", "Shayla", "Eira", "Zevra", "Ista", "Abra",
    )),
    "ru": frozenset((
        "Aglaya", "Anfisa", "Valentina", "Varvara", "Vera", "Galina", "Yevgenia",
        "Zoya", "Irina", "Ksenia", "Larisa", "Lidia", "Lukerya", "Maria", "Nadezhda",
        "Olga", "Praskovya", "Svetlana", "Tamara", "Ustinya", "Yarina",
    )),
    "us": frozenset((
        "Abigail", "Amanda", "Vivian", "Gloria", "Grace", "Dana", "Eden", "Lauren",
        "Madeline", "Maeve", "Melissa", "Priscilla", "Rita", "Stella", "Tessa", "Fiona",
        "Hazel", "Chloe", "Edith",
    )),
    "gb": frozenset((
        "Agnes", "Viola", "Grace", "Eden", "Clara", "Maeve", "Sorcha", "Tessa",
    )),
    "fr": frozenset((
        "Adeline", "Amélie", "Virginie", "Delphine", "Geneviève", "Yvette", "Colette",
        "Madeleine", "Margot", "Mireille", "Odile", "Rosalie", "Séverine", "Sylvie",
        "Chantal", "Éloïse", "Huguette",
    )),
    "de": frozenset((
        "Anneke", "Gerda", "Liselotte", "Svenja", "Ursula", "Heike",
    )),
    "it": frozenset((
        "Alice", "Gianna", "Letizia", "Nina", "Rosalba", "Fiore",
    )),
    "gr": frozenset((
        "Vasiliki", "Glykeria", "Dimitra", "Zoi", "Xenia", "Myrto", "Panagiota",
        "Fotini",
    )),
    "pl": frozenset((
        "Agnieszka", "Danuta", "Ewa", "Zdena", "Libuše", "Hanka", "Jadwiga",
    )),
    "no": frozenset((
        "Astrid", "Birutė", "Dagny", "Daina", "Jorunn", "Laima", "Lovisa", "Rasa",
        "Sigrid", "Solveig", "Ulla", "Freja", "Helga", "Eglė",
    )),
    "in": frozenset((
        "Amrita", "Anjali", "Ashmita", "Dhara", "Kavya", "Kumari", "Lakshmi", "Madhuri",
        "Neelam", "Nirmala", "Sunita", "Tara", "Chitra",
    )),
    "cn": frozenset((
        "Rulan", "Meiling", "Xiaoyan", "Han'er", "Shuiyin",
    )),
    "jp": frozenset((
        "Ayumi", "Izumi", "Keiko", "Natsumi", "Satomi", "Haruna",
    )),
    "kr": frozenset((
        "Ji-woo", "Young-hee", "Seon-mi", "Ha-eun", "Yu-na",
    )),
    "sea": frozenset((
        "Lan", "Ngoc", "Pranee", "Thao", "Lestari", "Nurul", "Siti", "Amihan",
        "Dalisay", "Lucinda", "Narra", "Sampaguita", "Tala",
    )),
    "tr": frozenset((
        "Azra", "Gülsen", "Lale", "Nesrin", "Fatma",
    )),
    "ar": frozenset((
        "Aisha", "Jamila", "Zahra", "Karima", "Layla", "Farida", "Habiba", "Yusra",
        "Anoush", "Goli", "Mehri", "Parvin", "Soheila", "Shirin",
    )),
    "il": frozenset((
        "Avital", "Dafna", "Miriam", "Naomi", "Rachel", "Tamar",
    )),
    "cauc": frozenset((
        "Darejan", "Ketevan", "Lali", "Nino", "Siranush",
    )),
    "turk": frozenset((
        "Ainur", "Gulmira", "Madina", "Saule", "Ulzhan", "Chinara",
    )),
    "wafr": frozenset((
        "Adjoa", "Ifeoma", "Mansata", "Ngozi", "Obioma", "Folake",
    )),
    "eafr": frozenset((
        "Asali", "Zaudi", "Neema", "Penda", "Khadija", "Abeba", "Desta", "Selam",
        "Hanna",
    )),
    "safr": frozenset((
        "Bongi", "Vivi", "Mbali", "Nolwazi",
    )),
    "latam": frozenset((
        "Benita", "Dulce", "Inés", "Carmen", "Lucía", "Manuela", "Mercedes", "Pilar",
        "Sol", "Ximena", "Juliana",
    )),
    "poly": frozenset((
        "Malia", "Moana", "Noelani", "Keala", "Ayasha", "Winona", "Sitsi",
    )),
}


FAMILY_F: dict[str, dict[str, str]] = {
    "ru": {
        "Aksyonov": "Aksyonova", "Belyaev": "Belyaeva", "Vorontsov": "Vorontsova",
        "Gagarin": "Gagarina", "Dementyev": "Dementyeva", "Yershov": "Yershova",
        "Zhukov": "Zhukova", "Zotov": "Zotova", "Ilyin": "Ilyina",
        "Kirillov": "Kirillova", "Kolesov": "Kolesova", "Luzhin": "Luzhina",
        "Mazurov": "Mazurova", "Nekrasov": "Nekrasova", "Ovchinnikov": "Ovchinnikova",
        "Pankratov": "Pankratova", "Prokhorov": "Prokhorova", "Rogozhin": "Rogozhina",
        "Savelyev": "Savelyeva", "Sotnikov": "Sotnikova", "Tarasov": "Tarasova",
        "Ushakov": "Ushakova", "Fomin": "Fomina", "Khabarov": "Khabarova",
        "Shcherbakov": "Shcherbakova", "Yurin": "Yurina", "Yakovlev": "Yakovleva",
    },
    "pl": {
        "Dvořák": "Dvořáková", "Kamiński": "Kamińska", "Kováč": "Kováčová",
        "Mazowiecki": "Mazowiecka", "Tesař": "Tesařová", "Hrudoš": "Hrudošová",
        "Červenka": "Červenková", "Jastrzębski": "Jastrzębska",
    },
}
