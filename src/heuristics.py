"""
heuristics.py
Camada 1 de classificação — regras hardcoded sem uso de IA.

REGRA PRINCIPAL:
    ÚTIL    = mídia pessoal (fotos, vídeos, áudios) + documentos pessoais
    LIXO    = executáveis, sistema, temporários, cache, instaladores
    AMBÍGUO = sem extensão ou formato proprietário raro → IA decide
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# LIXO — tudo que não é conteúdo pessoal
# ---------------------------------------------------------------------------

EXTENSOES_LIXO = {
    # Executáveis e instaladores
    ".exe", ".msi", ".com", ".scr", ".pif", ".apk", ".dmg", ".pkg",
    # Sistema Windows
    ".dll", ".sys", ".drv", ".ocx", ".cpl",
    ".inf", ".ini", ".reg", ".manifest",
    # Scripts de sistema
    ".bat", ".cmd", ".vbs", ".vbe", ".wsh", ".wsf", ".ps1",
    # Temporários e cache
    ".tmp", ".temp", ".bak", ".old", ".orig",
    ".log", ".log1", ".log2",
    ".dmp", ".etl", ".nfo",
    # Atalhos
    ".lnk", ".url", ".webloc",
    # Compilados e bytecode
    ".dll", ".pyd", ".pyc", ".pyo",
    ".obj", ".pdb", ".lib", ".a", ".o",
    ".class", ".jar",
    # Cache de apps
    ".cache", ".db-shm", ".db-wal",
    ".localstorage", ".localstorage-journal",
    # Windows app data
    ".appcontent-ms", ".settingcontent-ms",
    ".mui", ".onebin", ".odl", ".sqm",
    # Web/browser lixo
    ".eot", ".woff",                # web fonts de cache
    ".fbconsumer",                  # Facebook cache
    # Linux (inútil no Windows)
    ".so", ".d",
    # Índices e temporários de backup
    ".0", ".trs", ".fill", ".extra", ".dist", ".download",
    # DLLs renomeadas
    ".dll1", ".dll11", ".dll111", ".dll1111", ".dll11111",
    # Flash (obsoleto)
    ".swf",
    # Outros temporários
    ".swp", ".swo", ".lock", ".cab",
}

LIXO_NOMES = {
    "thumbs.db", "desktop.ini", ".ds_store",
    "pagefile.sys", "hiberfil.sys", "swapfile.sys",
    "ntuser.dat", "usrclass.dat",
    "autorun.inf",
}

# ---------------------------------------------------------------------------
# ÚTIL — apenas conteúdo pessoal que vale a pena guardar
# ---------------------------------------------------------------------------

EXTENSOES_UTEIS = {
    # Fotos e imagens pessoais
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif",
    ".heic", ".heif", ".webp", ".raw", ".cr2", ".nef", ".arw",
    ".ico", ".thm", ".icns", ".mpo", ".png0",
    ".psd", ".ai", ".cdr", ".dwg",             # design/vetor (pode ser trabalho)

    # Vídeos pessoais
    ".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".m4v", ".3gp",
    ".mpg", ".mpeg", ".ts", ".vob",
    ".lrv", ".mts", ".dav",                    # GoPro, AVCHD, DVR

    # Áudio pessoal
    ".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a",
    ".opus", ".amr",                            # WhatsApp/Telegram

    # Documentos pessoais
    ".pdf",
    ".doc", ".docx",
    ".xls", ".xlsx",
    ".ppt", ".pptx",
    ".odt", ".ods", ".odp",
    ".txt", ".rtf", ".csv", ".md",
    ".htm", ".html",
    ".chm",                                     # help files
    ".onetoc2",                                 # OneNote
    ".crypt12",                                 # backup WhatsApp

    # Código / projetos pessoais
    ".py", ".js", ".ts", ".css", ".json", ".xml",
    ".java", ".cpp", ".c", ".h", ".cs", ".php", ".rb", ".go",
    ".sql", ".sh", ".yaml", ".yml",
    ".xsl", ".xslt", ".mo",

    # Compactados (podem conter conteúdo útil)
    ".zip", ".rar", ".7z", ".tar", ".gz",

    # Banco de dados pessoal
    ".sqlite", ".db",

    # Projetos Corel/CAD
    ".jrs", ".fsd", ".ci3", ".cdrt", ".cdt", ".pat",

    # Fontes pessoais
    ".ttf", ".woff2",

    # Dados e backups importantes
    ".bin", ".dat", ".cpt",
}

# ---------------------------------------------------------------------------
# Mapeamento extensão → categoria (O(1))
# ---------------------------------------------------------------------------

CATEGORIAS: dict[str, str] = {
    **{e: "fotos" for e in {
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif",
        ".heic", ".heif", ".webp", ".raw", ".cr2", ".nef", ".arw",
        ".ico", ".thm", ".icns", ".mpo", ".png0", ".psd", ".ai", ".cdr", ".dwg",
    }},
    **{e: "videos" for e in {
        ".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".m4v", ".3gp",
        ".mpg", ".mpeg", ".ts", ".vob", ".lrv", ".mts", ".dav",
    }},
    **{e: "musica" for e in {
        ".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a",
        ".opus", ".amr",
    }},
    **{e: "documentos" for e in {
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        ".odt", ".ods", ".odp", ".txt", ".rtf", ".csv", ".md",
        ".htm", ".html", ".chm", ".onetoc2", ".crypt12",
    }},
    **{e: "projetos" for e in {
        ".py", ".js", ".ts", ".css", ".json", ".xml",
        ".java", ".cpp", ".c", ".h", ".cs", ".php", ".rb", ".go",
        ".sql", ".sh", ".yaml", ".yml", ".xsl", ".xslt", ".mo",
        ".jrs", ".fsd", ".ci3", ".cdrt", ".cdt", ".pat",
    }},
}


# ---------------------------------------------------------------------------
# Classificador principal
# ---------------------------------------------------------------------------

def classificar(caminho: Path, tamanho: int) -> dict:
    """
    Classifica um arquivo usando heurísticas.
    Retorna dict: status, categoria, confianca, metodo, motivo
    """
    nome = caminho.name.lower()
    ext  = caminho.suffix.lower()

    # 1. Nome exato de sistema
    if nome in LIXO_NOMES:
        return _r("lixo", "lixo_sistema", 1.0, f"Nome de sistema: {nome}")

    # 2. Sem extensão → ambíguo (IA decide)
    if not ext:
        return _r("ambiguo", None, 0.5, "Sem extensão — verificação manual recomendada")

    # 3. Extensão de lixo confirmado
    if ext in EXTENSOES_LIXO:
        return _r("lixo", "lixo_sistema", 0.97, f"Extensão de lixo: {ext}")

    # 4. Arquivo muito pequeno com extensão desconhecida → lixo provável
    if tamanho < 1024 and ext not in EXTENSOES_UTEIS:
        return _r("lixo", "lixo_sistema", 0.80, f"Arquivo < 1KB com extensão desconhecida ({ext})")

    # 5. Extensão útil reconhecida
    if ext in EXTENSOES_UTEIS:
        categoria = CATEGORIAS.get(ext, "outros")
        return _r("util", categoria, 0.93, f"Extensão reconhecida como útil: {ext}")

    # 6. Extensão desconhecida → IA
    return _r("ia_necessaria", None, 0.0, f"Extensão desconhecida: {ext}")


def _r(status: str, categoria, confianca: float, motivo: str) -> dict:
    return {
        "status":    status,
        "categoria": categoria,
        "confianca": confianca,
        "metodo":    "heuristica",
        "motivo":    motivo,
    }
