"""Universe definitions: IDX30, LQ45, and extended liquid stocks."""
from typing import List

# IDX30 — 30 saham likuiditas tertinggi (perkiraan komposisi 2026)
IDX30 = [
    "BBCA", "BBRI", "BMRI", "BBNI",  # Banking
    "TLKM", "ASII", "UNVR",           # Telco / Consumer / Conglomerate
    "BREN", "GOTO",                   # Energy / Tech
    "ANTM", "MDKA", "INCO", "TINS",   # Mining
    "ADRO", "PTBA", "ITMG", "HRUM",   # Energy / Coal
    "PGAS", "ESSA",                   # Energy
    "KLBF", "MIKA", "SIDO", "MYOR",   # Healthcare / Consumer
    "INDF", "CPIN", "AALI", "LSIP",   # Agro
    "SMGR", "INTP",                   # Cement
    "UNTR", "DOID",                   # Mining services / Coal
    "EXCL", "ISAT",                   # Telco
    "BMTR", "MAPI",                   # Media / Retail
]

# LQ45 — 45 saham likuid + fundamental kuat
LQ45 = list(dict.fromkeys(IDX30 + [
    "BRPT", "MEDC", "WTON", "JSMR",   # Construction / Energy / Toll
    "SMDR", "TOWR",                   # Property / Tower
    "BUMI", "BYAN",                   # Mining
    "AMMN", "NCKL", "MBAP",           # Mining / Nickel
    "ULTJ", "HEAL",                   # Food / Hospital
    "CTRA", "PWON", "BSDE",           # Property
    "SMRA", "AKRA",                   # Property / Energy
    "ICBP", "HMSP", "GGRM",           # Consumer / Tobacco
]))

# Extended liquid (150+ saham untuk scanning luas)
ALL_LIQUID = list(dict.fromkeys(LQ45 + [
    "ARTO", "BBTN", "BJBR", "BJTM", "BRIS", "BTPS", "NISP",
    "AGRO", "AUTO", "BALI", "BIRD", "BISI", "BLUE", "BOSS",
    "BRNA", "BSSR", "BUDI", "CAMP", "CARS", "CASS", "CEKA",
    "CLEO", "CMNP", "CPRI", "CSAP", "DILD", "DMAS", "DNET",
    "DSNG", "DSSA", "ELSA", "EMTK", "ENRG", "ERAA", "ESTI",
    "FILM", "FIRE", "FMII", "FOOD", "FPNI", "FREN", "GEMA",
    "GEMS", "GHON", "GIAA", "GJTL", "GOLD", "GPRA", "GWSA",
    "HAIS", "HELI", "HERO", "HEXA", "HKMU", "HOPE", "HOTL",
    "IBFN", "IBST", "ICON", "IDEA", "IGAR", "IKAI", "IKBI",
    "IMAS", "IMJS", "INAF", "INAI", "INCI", "INDR", "INDS",
    "INDX", "INDY", "INKP", "INPP", "INTD", "IPCC", "IPCM",
    "ISSP", "JAST", "JAWA", "JECC", "JGLE", "JIHD", "JKON",
    "KARW", "KAYU", "KEEN", "KIAS", "KIJA", "KINO", "KJEN",
    "KKGI", "KRAH", "KRAS", "KREN", "LAPD", "LCGP", "LEAD",
    "LINK", "LION", "LMAS", "LMPI", "LMSH", "LPCK", "LPGI",
    "LPIN", "LPKR", "LPLI", "LPPF", "LRNA", "LTLS", "MABA",
    "MAGP", "MAIN", "MAMI", "MAPA", "MAPB", "MARI", "MARK",
    "MASA", "MAYA", "MBSS", "MBTO", "MCAS", "MDCH", "MDKI",
    "MDLN", "MEGA", "MERK", "META", "MFIN", "MFMI", "MGNA",
    "MINA", "MIRA", "MITI", "MKNT", "MLBI", "MLIA", "MLPL",
    "MMLP", "MNCN", "MPMX", "MPPA", "MRAT", "MSIN", "MSKY",
    "MTDL", "MTFN", "MTLA", "MTSM", "MYOH", "MYRX", "MYTX",
    "NASA", "NELY", "NFCX", "NICK", "NIKL", "NIPS", "NOBU",
    "NRCA", "NTBK", "NUSA", "OBMD", "OCAP", "OILS", "OMRE",
    "OPMS", "PADI", "PALM", "PANR", "PANS", "PBID", "PBSA",
    "PDES", "PEGE", "PGLI", "PICO", "PJAA", "PKPK", "PLAN",
    "PLAS", "PMJS", "PMMP", "PNBS", "PNIN", "PNLF", "POLA",
    "POLI", "POLU", "POOL", "PORT", "POSA", "POWR", "PPRE",
    "PRAS", "PSAB", "PSGO", "PSKT", "PSSI", "PTIS", "PTPP",
    "PTRO", "PUDP", "PURA", "PYFA", "RALS", "RANC", "RBMS",
    "RDTX", "RELI", "RICY", "RIGS", "RMBA", "RODA", "ROTI",
    "RUIS", "SAFE", "SAME", "SATU", "SBAT", "SCMA", "SCNP",
    "SDMU", "SDPC", "SEMA", "SGER", "SGRO", "SHID", "SHIP",
    "SIAP", "SILO", "SIMA", "SIMP", "SINI", "SKBM", "SKLT",
    "SKRN", "SLIS", "SMAR", "SMBR", "SMCB", "SMDM", "SMKL",
    "SMMA", "SMMT", "SMRU", "SMSM", "SOCI", "SOLL", "SONA",
    "SPMA", "SPTO", "SQMI", "SRAJ", "SRIL", "SSIA", "SSMS",
    "SSTM", "STAR", "STTP", "SUGI", "SULI", "SUPR", "TALF",
    "TAMA", "TAMU", "TAPG", "TARA", "TBIG", "TCID", "TEBE",
    "TECH", "TELE", "TFCO", "TGKA", "TGRA", "TIFA", "TIRA",
    "TIRT", "TKIM", "TOBA", "TOPS", "TOTL", "TOYS", "TPIA",
    "TPMA", "TRIL", "TRIM", "TRIO", "TRIS", "TRST", "TRUE",
    "TUGU", "TURI", "UCID", "UFOE", "UNIC", "UNIT", "UNSP",
    "VICI", "VICO", "VIVA", "VOKS", "WEGE", "WICO", "WIIM",
    "WIKA", "WINS", "WIRG", "WMPP", "WOOD", "WOWS", "YELO",
    "YPAS", "YULE", "ZBRA", "ZINC", "ZONE",
]))


def get_universe(name: str = "LQ45") -> List[str]:
    """Return ticker list by universe name."""
    mapping = {
        "IDX30": IDX30,
        "LQ45": LQ45,
        "ALL_LIQUID": ALL_LIQUID,
    }
    return mapping.get(name.upper(), LQ45)
  
