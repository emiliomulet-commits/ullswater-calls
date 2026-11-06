#!/usr/bin/env python3
"""Recommend organisations with a track record for each open/forthcoming call.

Source: CORDIS open data (Horizon Europe + Horizon 2020 projects and participating
organisations), published by the European Commission under its reuse policy (CC BY 4.0).
Only organisation-level data is used: no personal data.

Method
1. Corpus = collaborative projects (single-beneficiary schemes such as ERC and MSCA
   fellowships are excluded) described by title + keywords + objective.
2. For each call, TF-IDF cosine similarity between the call text and every project,
   plus a bonus when the project's topic code belongs to the same programme family
   (e.g. HORIZON-CL4-…-DIGITAL-EMERGING).
3. Organisations are scored over the 60 most similar projects:
   similarity × recency × (1.5 if coordinator) — summed per organisation.
4. A "consortium archetype" is derived from the full consortia of the 25 most similar
   projects: median size, countries, organisation-type mix, SME share.

Output: data/partners.json (build-time data, rendered into the call pages).
"""
import io
import json
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache" / "cordis"
DATA = ROOT / "data"
SOURCES = {
    "HORIZON": "https://cordis.europa.eu/data/cordis-HORIZONprojects-csv.zip",
    "H2020": "https://cordis.europa.eu/data/cordis-h2020projects-csv.zip",
}
EXCLUDE_SCHEMES = re.compile(r"^(ERC|MSCA-IF|HORIZON-TMA-MSCA-PF|HORIZON-ERC|MSCA-PF|HORIZON-AG-UN|SME-1|EIC-SMEInst|HORIZON-EIC-ACC|SGA-CSA|HORIZON-COFUND)", re.I)
TYPES = {"HES": "University", "REC": "Research organisation", "PRC": "Company", "PUB": "Public body", "OTH": "Other"}
TOP_PROJECTS, TOP_ORGS, ARCH_PROJECTS = 60, 20, 25
MIN_SIM = 0.06


def load(fp):
    zpath = CACHE / f"{fp}.zip"
    if not zpath.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        print(f"Downloading CORDIS {fp}…")
        req = urllib.request.Request(SOURCES[fp], headers={"User-Agent": "UllswaterCallsBot/1.0"})
        zpath.write_bytes(urllib.request.urlopen(req, timeout=600).read())
    z = zipfile.ZipFile(zpath)

    def read(name):
        member = next(n for n in z.namelist() if n.endswith(name))
        return pd.read_csv(io.BytesIO(z.read(member)), sep=";", dtype=str, on_bad_lines="skip", quotechar='"')

    proj = read("project.csv")[["id", "acronym", "title", "startDate", "topics", "fundingScheme", "objective", "keywords", "ecMaxContribution"]]
    org = read("organization.csv")[["projectID", "organisationID", "name", "shortName", "SME", "activityType", "city", "country", "organizationURL", "role"]]
    proj["fp"] = fp
    return proj, org


def family(code):
    """HORIZON-CL4-2027-02-DIGITAL-EMERGING-05 -> {'HORIZON','CL4','DIGITAL','EMERGING'}"""
    toks = re.split(r"[-_.]", (code or "").upper())
    return {t for t in toks if t and not re.fullmatch(r"\d+", t) and t not in {"HORIZON", "H2020", "TWO", "STAGE"}}


def main():
    calls = json.loads((ROOT / "site" / "data" / "calls.json").read_text(encoding="utf-8"))["calls"]
    texts = json.loads((DATA / "topic_text.json").read_text(encoding="utf-8"))

    frames = [load(fp) for fp in SOURCES]
    proj = pd.concat([f[0] for f in frames], ignore_index=True).drop_duplicates("id")
    org = pd.concat([f[1] for f in frames], ignore_index=True)
    proj = proj[~proj["fundingScheme"].fillna("").str.match(EXCLUDE_SCHEMES)]
    sizes = org.groupby("projectID").size()
    proj = proj[proj["id"].map(sizes).fillna(0) >= 3].reset_index(drop=True)  # consortia only
    print(f"Corpus: {len(proj)} collaborative projects, {org['organisationID'].nunique()} organisations")

    proj["eu"] = pd.to_numeric(proj["ecMaxContribution"].fillna("").str.replace(",", ".", regex=False), errors="coerce")
    proj["year"] = pd.to_numeric(proj["startDate"].str[:4], errors="coerce").fillna(2015)
    recency = np.clip(1 - (2026 - proj["year"].to_numpy()) * 0.06, 0.4, 1.0)
    fam = [family(t) for t in proj["topics"].fillna("")]
    doc = (proj["title"].fillna("") + ". " + proj["keywords"].fillna("") + ". " + proj["objective"].fillna("")).tolist()

    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=3, max_df=0.4, sublinear_tf=True, max_features=300000)
    X = vec.fit_transform(doc)
    org_by_proj = {pid: g for pid, g in org.groupby("projectID")}
    org_recs = {pid: g.to_dict("records") for pid, g in org_by_proj.items()}
    out = {}

    for c in calls:
        text = texts.get(c["id"]) or (c["title"] + " " + c.get("summary", ""))
        q = vec.transform([text])
        sim = linear_kernel(q, X).ravel()
        cf = family(c["id"])
        if len(cf) >= 3:  # same programme family bonus (cluster + destination tokens)
            bonus = np.array([len(cf & f) / len(cf | f) if f else 0 for f in fam])
            sim = sim + 0.08 * bonus
        idx = np.argsort(-sim)[:TOP_PROJECTS]
        idx = [i for i in idx if sim[i] >= MIN_SIM]
        if len(idx) < 5:
            continue

        scores, info, counts = {}, {}, {}
        for i in idx:
            p = proj.iloc[i]
            for o in org_recs.get(p["id"], []):
                oid = o["organisationID"]
                w = sim[i] * recency[i] * (1.5 if o["role"] == "coordinator" else 1.0)
                scores[oid] = scores.get(oid, 0) + w
                counts[oid] = counts.get(oid, 0) + 1
                d = info.setdefault(oid, {"name": str(o["name"] or "").strip(), "country": o["country"], "type": o["activityType"],
                                          "sme": o["SME"] == "true", "city": str(o["city"] if isinstance(o["city"], str) else "").title(), "url": o["organizationURL"] if isinstance(o["organizationURL"], str) else None,
                                          "projects": [], "coord": 0})
                if o["role"] == "coordinator":
                    d["coord"] += 1
                if len(d["projects"]) < 3 and p["id"] not in [x["id"] for x in d["projects"]]:
                    d["projects"].append({"id": p["id"], "acronym": p["acronym"], "fp": p["fp"]})
        order = sorted(scores, key=lambda k: -scores[k])
        ranked = order[:TOP_ORGS]
        ranked_es = [k for k in order if info[k]["country"] == "ES"][:8]
        orgs, orgs_es = [], []
        for oid in dict.fromkeys(ranked + ranked_es):
            d = info[oid]
            d["n"] = counts[oid]
            d["score"] = round(float(scores[oid]), 3)
            if d["url"] and not d["url"].startswith("http"):
                d["url"] = "https://" + d["url"]
            if oid in ranked:
                orgs.append(d)
            if oid in ranked_es:
                orgs_es.append(d)

        # Consortium archetype from the closest projects
        arch_ids = [proj.iloc[i]["id"] for i in idx[:ARCH_PROJECTS]]
        cons = [org_by_proj[pid] for pid in arch_ids if pid in org_by_proj]
        type_mix = pd.concat(cons)["activityType"].value_counts(normalize=True)
        out[c["id"]] = {
            "orgs": orgs,
            "orgs_es": orgs_es,
            "max_sim": round(float(sim[idx[0]]), 3),
            "similar": [{"id": proj.iloc[i]["id"], "acronym": proj.iloc[i]["acronym"], "title": proj.iloc[i]["title"], "fp": proj.iloc[i]["fp"],
                         "year": int(proj.iloc[i]["year"]), "topic": proj.iloc[i]["topics"]} for i in idx[:6]],
            "funding": {
                "median_eu": int(np.nanmedian(proj.iloc[idx[:ARCH_PROJECTS]]["eu"].to_numpy())) if proj.iloc[idx[:ARCH_PROJECTS]]["eu"].notna().any() else None,
                "family_projects": int(sum(1 for i in range(len(fam)) if len(cf) >= 2 and fam[i] and len(cf & fam[i]) / len(cf | fam[i]) >= 0.66)),
                "family": "-".join(sorted(cf)) if len(cf) >= 2 else None,
            },
            "archetype": {
                "partners": int(np.median([len(g) for g in cons])),
                "countries": int(np.median([g["country"].nunique() for g in cons])),
                "sme_share": round(float(np.mean([(g["SME"] == "true").mean() for g in cons])), 2),
                "mix": {TYPES.get(k, k): round(float(v), 2) for k, v in type_mix.items() if k in TYPES},
                "based_on": len(cons),
            },
        }
    DATA.mkdir(exist_ok=True)
    (DATA / "partners.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Partner recommendations for {len(out)}/{len(calls)} calls")


if __name__ == "__main__":
    sys.exit(main())
