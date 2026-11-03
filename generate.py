#!/usr/bin/env python3
"""Gera profile.svg: janela estilo Macintosh II em verde fósforo, com a imagem do Tux e um "fetch" do perfil.

Uso:
  python generate.py          # busca as estatísticas na API do GitHub (precisa de token)
  python generate.py --demo   # usa números de exemplo, sem rede (para ver o layout)
  python generate.py --blank  # estatísticas como "--" (arquivo inicial, antes da primeira execução do Action)

Variáveis de ambiente: ACCESS_TOKEN (ou GITHUB_TOKEN) e USER_NAME.
"""
import base64, datetime, json, os, sys, urllib.request

# ----------------------------------------------------------------- conteúdo
CONFIG = {
    "header": "lucas@oliv",
    "os": "Omarchy",
    "uptime": "23 years, 4 months, 17 days",
    "host": "AB350M-DS3H V2",
    "kernel": "Linux 7.2.15-1-omarchy",
    "languages_programming": "Java, JavaScript, C++, Python",
    "languages_computer": "HTML, CSS, SQL, JSON, LaTeX",
    "languages_real": "Português, Inglês",
}

# ----------------------------------------------------------------- layout
IMG, GAP, INFO_COLS = 440, 22, 62   # imagem quadrada (px), espaço (px), colunas de texto
CW, LH, FS = 7.2, 14.5, 18          # largura do caractere, altura da linha, tamanho da fonte (VT323: 0,4 em)
WIN_PAD_X, WIN_PAD_Y = 20, 18
TITLE_H = 22
DESK = 14                          # margem da "mesa"

# paleta tirada da imagem do Tux (fósforo verde)
C = dict(desk="#070b06", screen="#0c110a", line="#8fb85a", bright="#c5e585", key="#9cc468",
         dots="#4a6a30", dim="#2b3d1c")

HERE = os.path.dirname(os.path.abspath(__file__))

# ----------------------------------------------------------------- estatísticas
API = "https://api.github.com/graphql"

def gql(query, variables, token):
    req = urllib.request.Request(
        API, data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "profile-svg"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    if "errors" in data:
        raise RuntimeError(json.dumps(data["errors"])[:500])
    return data["data"]

def fetch_stats(login, token):
    u = gql("""query($l:String!){ user(login:$l){ id createdAt followers{totalCount}
        repositories(ownerAffiliations:OWNER){totalCount}
        repositoriesContributedTo(contributionTypes:[COMMIT,PULL_REQUEST,ISSUE,REPOSITORY]){totalCount} } }""",
        {"l": login}, token)["user"]
    # estrelas nos repositórios próprios
    stars, after = 0, None
    while True:
        d = gql("""query($l:String!,$a:String){ user(login:$l){ repositories(first:100, after:$a, ownerAffiliations:OWNER){
            nodes{stargazerCount} pageInfo{hasNextPage endCursor} } } }""", {"l": login, "a": after}, token)["user"]["repositories"]
        stars += sum(n["stargazerCount"] for n in d["nodes"])
        if not d["pageInfo"]["hasNextPage"]: break
        after = d["pageInfo"]["endCursor"]
    # commits: a API limita cada consulta a 1 ano
    now = datetime.datetime.now(datetime.timezone.utc)
    commits = 0
    for year in range(int(u["createdAt"][:4]), now.year + 1):
        a = f"{year}-01-01T00:00:00Z"
        b = min(datetime.datetime(year + 1, 1, 1, tzinfo=datetime.timezone.utc), now).strftime("%Y-%m-%dT%H:%M:%SZ")
        c = gql("""query($l:String!,$f:DateTime!,$t:DateTime!){ user(login:$l){ contributionsCollection(from:$f,to:$t){
            totalCommitContributions restrictedContributionsCount } } }""", {"l": login, "f": a, "t": b}, token)
        cc = c["user"]["contributionsCollection"]
        commits += cc["totalCommitContributions"] + cc["restrictedContributionsCount"]
    # linhas de código: soma additions/deletions dos seus commits no branch padrão de cada repositório
    repos, after = [], None
    while True:
        d = gql("""query($l:String!,$a:String){ user(login:$l){ repositories(first:50, after:$a, ownerAffiliations:[OWNER,COLLABORATOR]){
            nodes{name owner{login}} pageInfo{hasNextPage endCursor} } } }""", {"l": login, "a": after}, token)["user"]["repositories"]
        repos += [(n["owner"]["login"], n["name"]) for n in d["nodes"]]
        if not d["pageInfo"]["hasNextPage"]: break
        after = d["pageInfo"]["endCursor"]
    add = dele = 0
    for owner, name in repos:
        after = None
        while True:
            d = gql("""query($o:String!,$n:String!,$id:ID!,$a:String){ repository(owner:$o,name:$n){ defaultBranchRef{ target{
                ... on Commit{ history(first:100, after:$a, author:{id:$id}){ pageInfo{hasNextPage endCursor} nodes{additions deletions} } } } } } }""",
                {"o": owner, "n": name, "id": u["id"], "a": after}, token)["repository"]
            ref = d["defaultBranchRef"]
            if not ref: break
            h = ref["target"]["history"]
            for n in h["nodes"]:
                add += n["additions"]; dele += n["deletions"]
            if not h["pageInfo"]["hasNextPage"]: break
            after = h["pageInfo"]["endCursor"]
    return dict(repos=u["repositories"]["totalCount"], contributed=u["repositoriesContributedTo"]["totalCount"],
                stars=stars, commits=commits, followers=u["followers"]["totalCount"], add=add, dele=dele)

BLANK = dict(repos="--", contributed="--", stars="--", commits="--", followers="--", add="--", dele="--")
DEMO = dict(repos=12, contributed=14, stars=3, commits=214, followers=5, add=18420, dele=3310)

# ----------------------------------------------------------------- texto das linhas
fmt = lambda n: n if isinstance(n, str) else f"{n:,}"

# cada linha é uma lista de trechos (texto, classe): d = pontos/pontuação, k = chave, v = valor
def kv(key, value, cols=INFO_COLS):
    left = f". {key}: "
    dots = cols - len(left) - 1 - len(value)
    assert dots >= 3, f"valor longo demais em {key}"
    return [(". ", "d"), (key, "k"), (": ", "d"), ("." * dots + " ", "d"), (value, "v")]

def half(label, value, width, bullet):
    left = (". " if bullet else "") + f"{label}: "
    dots = width - len(left) - 1 - len(value)
    assert dots >= 1, f"valor longo demais em {label}"
    segs = [(". ", "d")] if bullet else []
    return segs + [(label, "k"), (": ", "d"), ("." * dots + " ", "d"), (value, "v")]

def info_lines(st):
    c = CONFIG
    w1 = 36
    repos_v = f"{fmt(st['repos'])} {{Contributed: {fmt(st['contributed'])}}}"
    if isinstance(st["add"], str):
        loc_v = "-- ( --++, ---- )"
    else:
        loc_v = f"{fmt(st['add'] - st['dele'])} ( {fmt(st['add'])}++, {fmt(st['dele'])}-- )"
    loc_label = "Lines of Code on GitHub"
    if len(f". {loc_label}: ") + 4 + len(loc_v) > INFO_COLS:
        loc_label = "Lines of Code"
    sep = [(" | ", "d")]
    return [
        ("hdr", c["header"]),
        ("segs", kv("OS", c["os"])),
        ("segs", kv("Uptime", c["uptime"])),
        ("segs", kv("Host", c["host"])),
        ("segs", kv("Kernel", c["kernel"])),
        ("blank", None),
        ("segs", kv("Languages.Programming", c["languages_programming"])),
        ("segs", kv("Languages.Computer", c["languages_computer"])),
        ("segs", kv("Languages.Real", c["languages_real"])),
        ("blank", None),
        ("hdr", "GitHub Stats"),
        ("segs", half("Repos", repos_v, w1, True) + sep + half("Stars", fmt(st["stars"]), INFO_COLS - w1 - 3, False)),
        ("segs", half("Commits", fmt(st["commits"]), w1, True) + sep + half("Followers", fmt(st["followers"]), INFO_COLS - w1 - 3, False)),
        ("segs", kv(loc_label, loc_v)),
    ]

# ----------------------------------------------------------------- SVG
esc = lambda s: s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
b64 = lambda *p: base64.b64encode(open(os.path.join(HERE, *p), "rb").read()).decode()

def build(st):
    info = info_lines(st)
    info_h = len(info) * LH
    rows_h = max(IMG, info_h)
    content_w = IMG + GAP + INFO_COLS * CW
    win_w = content_w + 2 * WIN_PAD_X
    win_h = TITLE_H + 2 * WIN_PAD_Y + rows_h
    W, H = win_w + 2 * DESK + 3, win_h + 2 * DESK + 3
    wx = wy = DESK
    cx, cy = wx + WIN_PAD_X, wy + TITLE_H + WIN_PAD_Y
    info_x = cx + IMG + GAP
    info_y0 = cy + (rows_h - info_h) / 2

    o = [f'<?xml version="1.0" encoding="UTF-8"?>',
         f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W:.0f}" height="{H:.0f}" '
         f'viewBox="0 0 {W:.0f} {H:.0f}" role="img" aria-label="Terminal estilo Macintosh II com o Tux, a GNU General Public License e o perfil de lucas@oliv: Omarchy, Java, JavaScript, C++, Python, HTML, CSS, SQL, JSON, LaTeX, Português, Inglês">',
         f'<style>@font-face{{font-family:"VT323";src:url(data:font/woff2;base64,{b64("fonts","vt323-latin-400-normal.woff2")}) format("woff2");}}'
         f'.t{{font-family:"VT323","Courier New",ui-monospace,monospace;font-size:{FS}px;white-space:pre}}'
         f'.d{{fill:{C["dots"]}}}.k{{fill:{C["key"]}}}.v{{fill:{C["bright"]}}}.i{{fill:{C["screen"]}}}</style>',
         f'<rect width="{W:.0f}" height="{H:.0f}" fill="{C["desk"]}"/>',
         f'<rect x="{wx+3}" y="{wy+3}" width="{win_w:.0f}" height="{win_h:.0f}" fill="#000"/>',
         f'<rect x="{wx+0.5}" y="{wy+0.5}" width="{win_w:.0f}" height="{win_h:.0f}" fill="{C["screen"]}" stroke="{C["line"]}" stroke-width="1.5"/>']
    # barra de título listrada
    for i in range(6):
        y = wy + 4.5 + i * 3
        o.append(f'<line x1="{wx+2}" y1="{y}" x2="{wx+win_w-1}" y2="{y}" stroke="{C["line"]}" stroke-width="1" shape-rendering="crispEdges"/>')
    o.append(f'<line x1="{wx}" y1="{wy+TITLE_H}" x2="{wx+win_w}" y2="{wy+TITLE_H}" stroke="{C["line"]}" stroke-width="1.5"/>')
    o.append(f'<rect x="{wx+9}" y="{wy+4.5}" width="13" height="13" fill="{C["screen"]}" stroke="{C["line"]}" stroke-width="1.5"/>')
    title = CONFIG["header"]
    tw = (len(title) + 2) * CW
    tx = wx + win_w / 2
    o.append(f'<rect x="{tx-tw/2:.1f}" y="{wy+2}" width="{tw:.1f}" height="{TITLE_H-4}" fill="{C["screen"]}"/>')
    o.append(f'<text class="t v" x="{tx:.1f}" y="{wy+TITLE_H-5}" text-anchor="middle">{esc(title)}</text>')

    # imagem do Tux (embutida, pois SVG usado como <img> não carrega arquivos externos)
    iy = cy + (rows_h - IMG) / 2
    o.append(f'<image x="{cx}" y="{iy:.1f}" width="{IMG}" height="{IMG}" preserveAspectRatio="xMidYMid slice" '
             f'xlink:href="data:image/jpeg;base64,{b64("assets","tux.jpg")}"/>')
    o.append(f'<rect x="{cx-0.5}" y="{iy-0.5:.1f}" width="{IMG+1}" height="{IMG+1}" fill="none" stroke="{C["line"]}" stroke-width="1"/>')

    # informações
    full = INFO_COLS * CW
    for i, (kind, data) in enumerate(info):
        if kind == "blank":
            continue
        y = info_y0 + i * LH + FS * 0.62
        if kind == "hdr":
            n = len(data) + 1
            o.append(f'<rect x="{info_x:.1f}" y="{y-FS*0.6:.1f}" width="{n*CW:.1f}" height="{LH-1}" fill="{C["bright"]}"/>')
            o.append(f'<text class="t" x="{info_x:.1f}" y="{y:.1f}" textLength="{full:.1f}" lengthAdjust="spacing">'
                     f'<tspan class="i">{esc(data)} </tspan><tspan class="d">{"-" * (INFO_COLS - n)}</tspan></text>')
        else:
            assert sum(len(t) for t, _ in data) == INFO_COLS, "linha com largura errada"
            spans = "".join(f'<tspan class="{c}">{esc(t)}</tspan>' for t, c in data)
            o.append(f'<text class="t" x="{info_x:.1f}" y="{y:.1f}" textLength="{full:.1f}" lengthAdjust="spacing">{spans}</text>')
    o.append('</svg>')
    return "\n".join(o)

def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "--demo":
        st, name = DEMO, "profile_demo.svg"
    elif arg == "--blank":
        st, name = BLANK, "profile.svg"
    else:
        token = os.environ.get("ACCESS_TOKEN") or os.environ.get("GITHUB_TOKEN")
        login = os.environ.get("USER_NAME")
        if not token or not login:
            sys.exit("Defina ACCESS_TOKEN (ou GITHUB_TOKEN) e USER_NAME, ou use --demo / --blank.")
        st, name = fetch_stats(login, token), "profile.svg"
    open(os.path.join(HERE, name), "w", encoding="utf-8").write(build(st))
    print("gerado:", name, st)

if __name__ == "__main__":
    main()
