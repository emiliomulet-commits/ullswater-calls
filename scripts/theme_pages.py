"""Thematic landing pages (/theme/<slug>/) that replace the old Google Sites call pages
of www.ullswaterinvestments.com/calls/... They are rebuilt with the live data on every run."""
import re

AI_CASE = re.compile(r"\bAI\b|\bGenAI\b")


def _text(c):
    return " ".join([c.get("title") or "", c.get("summary") or "", c.get("callTitle") or "", " ".join(c.get("tags") or [])])


def _pre(c, *prefixes):
    i = (c.get("id") or "").upper()
    return any(i.startswith(p) for p in prefixes)


def _is_ai(c):
    t = _text(c)
    return bool(AI_CASE.search(t) or re.search(r"artificial intelligence|generative|machine learning|foundation model|large language model|robotic", t, re.I)) or _pre(c, "HORIZON-RAISE")


# (slug, title, short name, intro, old Google Sites path, predicate)
THEMES = [
    ("generative-ai", "AI and generative AI calls", "AI & GenAI",
     "Open and forthcoming EU calls on artificial intelligence, generative AI, data and robotics, across Horizon Europe, Digital Europe and other programmes.",
     "/calls/calls-for-genai", _is_ai),
    ("eic", "European Innovation Council (EIC) calls", "EIC",
     "EIC Accelerator, Pre-Accelerator, Pathfinder, Transition and STEP calls for start-ups, SMEs and research teams with breakthrough technologies.",
     "/calls/eic-pre-accelerator", lambda c: "EIC" in (c.get("id") or "").upper()),
    ("closing-this-year", "EU calls closing before the end of the year", "Closing this year",
     "Every open or forthcoming EU call whose next deadline falls before 31 December of the current year.",
     "/calls/calls-2026", None),  # predicate set at build time (depends on the year)
    ("cascade-funding", "Cascade funding (FSTP) open calls", "Cascade funding",
     "Open calls for third parties run by EU-funded projects: smaller grants, lighter applications and fast decisions, ideal for SMEs and start-ups.",
     "/calls/cascade-funding", lambda c: c.get("kind") == "cascade"),
    ("health", "Health calls: Horizon Europe Cluster 1, IHI and EU4Health", "Health",
     "Calls of Horizon Europe Cluster 1 (Health), the Innovative Health Initiative and EU4Health.",
     "/calls/horizon-health", lambda c: _pre(c, "HORIZON-HLTH", "HORIZON-JU-IHI") or c.get("programme") == "EU4H"),
    ("culture-society", "Culture, creativity and inclusive society calls (Cluster 2)", "Culture & Society",
     "Horizon Europe Cluster 2 calls on democracy, cultural heritage and social and economic transformations.",
     "/calls/horizon-society", lambda c: _pre(c, "HORIZON-CL2")),
    ("civil-security", "Civil security for society calls (Cluster 3)", "Civil Security",
     "Horizon Europe Cluster 3 calls on disaster resilience, border management, fighting crime and cybersecurity.",
     "/calls/horizon-security", lambda c: _pre(c, "HORIZON-CL3")),
    ("digital-industry-space", "Digital, industry and space calls (Cluster 4)", "Digital, Industry & Space",
     "Horizon Europe Cluster 4 calls on AI, data, chips, quantum, advanced materials, manufacturing and space, plus the EuroHPC, Chips and SNS joint undertakings.",
     "/calls/horizon-digital", lambda c: _pre(c, "HORIZON-CL4", "HORIZON-JU-EUROHPC", "HORIZON-JU-CHIPS", "HORIZON-JU-SNS")),
    ("climate-energy-mobility", "Climate, energy and mobility calls (Cluster 5)", "Climate, Energy & Mobility",
     "Horizon Europe Cluster 5 calls on clean energy, batteries, buildings, transport and climate science, plus the related joint undertakings.",
     "/calls/horizon-climate-energy", lambda c: _pre(c, "HORIZON-CL5", "HORIZON-JU-CLEAN", "HORIZON-JU-CCAM", "HORIZON-JU-ER", "HORIZON-JU-SESAR")),
    ("food-environment", "Food, bioeconomy, natural resources and environment calls (Cluster 6)", "Food & Environment",
     "Horizon Europe Cluster 6 and biodiversity calls on farming, food systems, oceans, circular bio-based industries and nature, plus LIFE.",
     "/calls/horizon-food-environment", lambda c: _pre(c, "HORIZON-CL6", "HORIZON-NATURE", "HORIZON-JU-CBE") or c.get("programme") == "LIFE"),
    ("missions-bridging", "EU Missions, New European Bauhaus and bridging calls", "Missions & Bridging",
     "Calls of the five EU Missions, the New European Bauhaus facility and the cross-cluster bridging calls.",
     "/calls/horizon-missions", lambda c: _pre(c, "HORIZON-MISS", "HORIZON-NEB", "HORIZON-BRIDGING", "HORIZON-CID")),
    ("science-widening", "Excellent science and widening participation calls", "Science & Widening",
     "MSCA, ERC, research infrastructures, Widening participation, EIT, European innovation ecosystems and RAISE calls.",
     "/calls/horizon-science-widening", lambda c: _pre(c, "HORIZON-MSCA", "ERC", "HORIZON-ERC", "HORIZON-INFRA", "HORIZON-WIDERA", "HORIZON-EIT", "HORIZON-EIE", "HORIZON-RAISE")),
    ("digital-europe-defence", "Digital Europe and European Defence Fund calls", "Digital Europe & Defence",
     "Digital Europe deployment calls (AI, cybersecurity, skills, data spaces) and the European Defence Fund and EDIP.",
     "/calls/digital-europe-defence", lambda c: c.get("programme") in ("DIGITAL", "EDF")),
    ("other-eu-programmes", "Other EU programmes: Creative Europe, CERV, Erasmus+, CEF and more", "Other EU programmes",
     "Calls of Creative Europe, CERV, Erasmus+, I3, CEF, ISF, Single Market, Justice and other EU programmes.",
     "/calls/other-eu-programmes", lambda c: c.get("programme") not in ("HORIZON", "DIGITAL", "EDF", "NDICI", "HUMA")),
    ("international-cooperation", "International cooperation calls (Global Europe and humanitarian aid)", "International cooperation",
     "Calls managed by EU Delegations under Global Europe (NDICI) and humanitarian aid.",
     "/calls/international-cooperation", lambda c: c.get("programme") in ("NDICI", "HUMA")),
]


def build(calls, year):
    """Return [(slug, title, short, intro, old_path, matching calls)]."""
    out = []
    for slug_, title, short, intro, old, pred in THEMES:
        if pred is None:
            pred = (lambda c: bool(c.get("deadline")) and c["deadline"][:4] == str(year))
        out.append((slug_, title, short, intro, old, [c for c in calls if pred(c)]))
    return out
