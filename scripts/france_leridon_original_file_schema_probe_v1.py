#!/usr/bin/env python3
"""Schema-only local probe for an *actual* Henri Leridon Academy historical file.

Does NOT require or fabricate an unavailable 3218-row original. Accepts CSV,
TSV and modern Excel XLSX, and reports DOCX structure (no tabular import).
No network, no DOB-person output, no admission of Academy member categories,
no astrological/BaZi variables.

XLSX reader uses Python stdlib zipped Office Open XML in READ-ONLY fashion:
no macros, links, formulas, add-ins, packages, or external URLs are executed.
Source data is NEVER modified. Aggregate audit only, kept in local_runs/.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import posixpath
import re
import sys
import tempfile
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

VERSION = "france-academy-leridon-local-source-schema-probe-v1"
OUT = Path("local_runs/france_academy_leridon_original_file_probe_v1")
REQUIRED = {"NOM","ENTREE","SUITE","DATNAIS","DATENTREE"}
ALIASES={
    "NOM":{"nom","nom prenom","nom prenoms","name"},
    "ENTREE":{"entree","grade entree","premiere entree"},
    "SUITE":{"suite","grades suivants","grade suivant"},
    "DECES":{"deces","mort","mort date"},
    "DATNAIS":{"datnais","date de naissance","dat naissance"},
    "DATENTREE":{"datentree","date dentree","date entree"},
    "PAYSNAIS":{"paysnais","pays naissance"},
    "ETRANGER":{"etranger","nationalite"},
    "FEMME":{"femme","sexe"},
}
XLSX_NS="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_NS="http://schemas.openxmlformats.org/package/2006/relationships"
W_NS="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
MAX_INPUT_BYTES=65_000_000
MAX_ZIP_UNCOMPRESSED=320_000_000
MAX_SHEET_ROWS=200_000
MAX_COLS=200
MAX_SHARED=200_000
PRIVACY_NOTE="Output records only field names and aggregates; never names, individual DOBs, or person-level statuses."


def file_sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1<<20),b""):
            h.update(block)
    return h.hexdigest()


def norm(v)->str:
    s=unicodedata.normalize("NFKD",str(v or "").strip().casefold())
    s="".join(c for c in s if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+",s))


def detect_canonical_header(cell)->str|None:
    n=norm(cell)
    for ident,spellings in ALIASES.items():
        if n in spellings:return ident
    return None


def detect_header(rows:list[list])->tuple[int,dict[str,int],int]:
    """Check only first 25 rows; never derive source schema from assumed indexes."""
    best=(-1,{},0)
    for row_idx,row in enumerate(rows[:25]):
        matched={}
        for idx,cell in enumerate(row[:MAX_COLS]):
            key=detect_canonical_header(cell)
            if key and key not in matched:matched[key]=idx
        score=len(matched)
        if score>best[2]:
            best=(row_idx,matched,score)
    return best


def month_date_quality(value:str)->str:
    """Source DOB field precision only, not accepted birthdate evidence."""
    value=str(value or "").strip()
    if not value:return "blank"
    if value in {"00/00/0000","0/0/0000","0000-00-00","0000"}:
        return "explicit_unknown_sentinel"
    m=re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})",value)
    if m:
        day,month,year=map(int,m.groups())
        try:dt.date(year,month,day)
        except ValueError:return "invalid_calendar_date"
        return "day_precision_text_candidate"
    m=re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})",value)
    if m:
        year,month,day=map(int,m.groups())
        try:dt.date(year,month,day)
        except ValueError:return "invalid_calendar_date"
        return "day_precision_text_candidate"
    if re.fullmatch(r"(?:1[6789]\d{2}|20\d{2})",value):
        return "year_only"
    if re.fullmatch(r"\d{4}[-/]\d{1,2}",value):
        return "year_month_only"
    if re.fullmatch(r"\d+(?:[.,]\d+)?",value):
        return "numeric_excel_date_serial_or_number_REVIEW"
    return "freeform_date_requires_review"


def inspect_rows(rows:list[list], *, origin:str, snapshot_sha:str, source_format:str,
                 selected_sheet:str="")->dict:
    headidx,cols,score=detect_header(rows)
    census=Counter()
    roles=Counter()
    candidates=[]
    if score:
        for row in rows[headidx+1:]:
            if not any(str(x).strip() for x in row):
                continue
            census["nonempty_rows_after_header"]+=1
            if census["nonempty_rows_after_header"]>MAX_SHEET_ROWS:
                raise RuntimeError("Input has unexpectedly large number of people rows")
            for ident,idx in cols.items():
                cell=str(row[idx] if idx<len(row) else "").strip()
                if cell:census["field_"+ident+"_nonempty"]+=1
                else:census["field_"+ident+"_empty"]+=1
                if ident in ("DATNAIS","DATENTREE"):
                    census[ident+"_quality_"+month_date_quality(cell)]+=1
            # Metadata-only gross role-word frequencies: need ENTREE+SUITE
            # actual original string and source-era nomenclature for adjudication.
            for ident in ("ENTREE","SUITE"):
                if ident not in cols:continue
                idx=cols[ident]
                text=norm(row[idx] if idx<len(row) else "")
                if "correspondant" in text:roles[ident+"_mentions_correspondant"]+=1
                if "associe" in text and "etranger" in text:roles[ident+"_mentions_foreign_associate"]+=1
                if "membre" in text:roles[ident+"_mentions_membre"]+=1
        header_status="FIVE_CORE_FIELDS_DETECTED" if REQUIRED.issubset(cols) else "PARTIAL_FIELDS_REQUIRE_USER_REVIEW"
    else:
        header_status="NO_RECOGNIZABLE_LERIDON_HEADER_FOUND"
    # Output deliberately excludes row contents and names.
    return {
        "source_sha256":snapshot_sha,
        "source_basename_only":Path(origin).name,
        "input_source_format":source_format,
        "selected_sheet":selected_sheet,
        "header_row_one_based":headidx+1 if score else None,
        "header_match_count":score,
        "recognized_fields_and_columns_zero_based":dict(sorted(cols.items())),
        "schema_status":header_status,
        "nonempty_data_rows":census["nonempty_rows_after_header"],
        "file_row_count_including_header_and_blank":len(rows),
        "field_nonempty_and_date_precision_counts":dict(sorted(census.items())),
        "raw_role_term_mention_counts_not_adjudicated":dict(sorted(roles.items())),
        "source_3218_original_rows_authenticated":False,
        "rows_eligible_for_study_accepted":0,
        "independent_DOBs_accepted":0,
        "bazi_variables_computed":0,
        "privacy":PRIVACY_NOTE,
    }


def read_csv_rows(path:Path)->tuple[list[list],str]:
    raw=path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        text=raw.decode("utf-8-sig")
        encoding="utf-8-sig"
    else:
        try:text=raw.decode("utf-8");encoding="utf-8"
        except UnicodeDecodeError:
            text=raw.decode("cp1252",errors="strict")
            encoding="cp1252-fallback_REVIEW"
    candidate=text[:5000]
    try:delim=csv.Sniffer().sniff(candidate,delimiters=",;\t|").delimiter
    except csv.Error:delim="\t" if path.suffix.lower()==".tsv" else ","
    rows=list(csv.reader(io.StringIO(text),delimiter=delim))
    if len(rows)>MAX_SHEET_ROWS or any(len(r)>MAX_COLS for r in rows[:30]):
        raise RuntimeError("Unexpectedly large CSV/TSV")
    return rows,encoding


def read_ooxml(path:Path)->list[dict]:
    """Read small/medium XLSX worksheets with zip/XML only; never evaluate."""
    out=[]
    with zipfile.ZipFile(path) as z:
        infos=z.infolist()
        total=sum(i.file_size for i in infos)
        if total>MAX_ZIP_UNCOMPRESSED or len(infos)>5000:
            raise RuntimeError("Office ZIP input too big; refuse")
        names={i.filename for i in infos}
        if "xl/workbook.xml" not in names or "xl/_rels/workbook.xml.rels" not in names:
            raise RuntimeError("Not a normal OOXML Excel workbook")
        shared=[]
        if "xl/sharedStrings.xml" in names:
            root=ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall(f"{{{XLSX_NS}}}si"):
                v="".join(t.text or "" for t in si.iter(f"{{{XLSX_NS}}}t"))
                shared.append(v)
                if len(shared)>MAX_SHARED:raise RuntimeError("Huge sharedStrings table")
        relationships={}
        rels=ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        for e in rels.findall(f"{{{PKG_NS}}}Relationship"):
            if e.attrib.get("TargetMode")=="External":continue
            target=e.attrib.get("Target","")
            if target.startswith("/"):
                safe=target.lstrip("/")
            else:
                safe=posixpath.normpath(posixpath.join("xl",target))
            if safe in names and safe.startswith("xl/worksheets/") and safe.endswith(".xml"):
                relationships[e.attrib.get("Id")]=safe
        wb=ET.fromstring(z.read("xl/workbook.xml"))
        sheets=wb.find(f"{{{XLSX_NS}}}sheets")
        if sheets is None:raise RuntimeError("OOXML has no worksheets")
        for sheet in list(sheets)[:32]:
            name=sheet.attrib.get("name","")
            relationship_id=sheet.attrib.get(f"{{{REL_NS}}}id")
            internal=relationships.get(relationship_id)
            if not internal:continue
            rows=[]
            # For 3,218 people × dozens of columns, source is small enough for
            # read-only row matrix. Max caps guard unexpected giant workbooks.
            with z.open(internal) as fp:
                xmlroot=None
                for _,elem in ET.iterparse(fp,events=("end",)):
                    if elem.tag != f"{{{XLSX_NS}}}row":
                        continue
                    row={}
                    for c in elem.findall(f"{{{XLSX_NS}}}c"):
                        cell_ref=c.attrib.get("r","")
                        cm=re.match(r"([A-Z]{1,3})",cell_ref)
                        if cm is None:continue
                        index=0
                        for v in cm.group(1):index=index*26+ord(v)-ord("A")+1
                        index-=1
                        if index>=MAX_COLS:continue
                        typ=c.attrib.get("t","")
                        val=c.find(f"{{{XLSX_NS}}}v")
                        if typ=="inlineStr":
                            inline=c.find(f"{{{XLSX_NS}}}is")
                            text="".join(t.text or "" for t in inline.iter(f"{{{XLSX_NS}}}t")) if inline is not None else ""
                        else:
                            text=val.text if val is not None and val.text is not None else ""
                            if typ=="s" and text:
                                try:text=shared[int(text)]
                                except (ValueError,IndexError):
                                    raise RuntimeError("Shared string index invalid")
                        row[index]=text
                    line=[""]*(min(MAX_COLS,max(row)+1)) if row else []
                    for i,v in row.items():line[i]=v
                    rows.append(line)
                    elem.clear()
                    if len(rows)>MAX_SHEET_ROWS:raise RuntimeError("Sheet has too many rows")
            out.append({"sheet_name":name,"source_xml_path":internal,"rows":rows})
    if not out:raise RuntimeError("No nonexternal XLSX source worksheets")
    return out


def inspect_docx(path:Path)->dict:
    with zipfile.ZipFile(path) as z:
        if "word/document.xml" not in z.namelist():
            raise RuntimeError("Not valid DOCX")
        root=ET.fromstring(z.read("word/document.xml"))
        paragraphs=root.findall(f".//{{{W_NS}}}p")
        tables=root.findall(f".//{{{W_NS}}}tbl")
        fragments=[]
        for p in paragraphs[:30000]:
            txt="".join(x.text or "" for x in p.iter(f"{{{W_NS}}}t"))
            fragments.append(txt)
        vocabulary=Counter()
        for s in fragments:
            for ident in ALIASES:
                if norm(s).upper()==ident:vocabulary[ident]+=1
        return {
            "docx_paragraphs":len(paragraphs),
            "docx_tables":len(tables),
            "field_label_line_occurrences_not_person_rows":dict(vocabulary),
            "schema_status":"DOCX_LAYOUT_REQUIRES_SEPARATE_PRE_REGISTERED_PARSER",
            "source_3218_original_rows_authenticated":False,
            "rows_eligible_for_study_accepted":0,
            "independent_DOBs_accepted":0,
            "bazi_variables_computed":0,
        }


def inspect_path(path:Path)->dict:
    if not path.is_file():raise FileNotFoundError(path)
    if path.stat().st_size>MAX_INPUT_BYTES:
        raise RuntimeError("Source file exceeds schema-probe maximum size")
    suffix=path.suffix.lower()
    h=file_sha(path)
    if suffix in (".csv",".tsv"):
        rows,encoding=read_csv_rows(path)
        record=inspect_rows(rows,origin=path.name,snapshot_sha=h,source_format=suffix.lstrip("."))
        record["encoding_used"]=encoding
        return {"source_info":record,"alternatives":[]}
    if suffix in (".xlsx",".xlsm"):
        sheets=read_ooxml(path)
        records=[inspect_rows(s["rows"],origin=path.name,snapshot_sha=h,
                              source_format=suffix.lstrip("."),selected_sheet=s["sheet_name"])
                 for s in sheets]
        ranked=sorted(records,key=lambda r:(-r["header_match_count"],-r["nonempty_data_rows"],r["selected_sheet"]))
        return {"source_info":ranked[0],"alternatives":[
            {"sheet_name":x["selected_sheet"],"header_match_count":x["header_match_count"],
             "number_of_nonempty_rows":x["nonempty_data_rows"]} for x in ranked[1:]]}
    if suffix==".docx":
        record=inspect_docx(path)
        record["source_basename_only"]=path.name
        record["source_sha256"]=h
        record["input_source_format"]="docx"
        return {"source_info":record,"alternatives":[]}
    if suffix in (".doc",".xls"):
        return {"source_info":{
            "source_basename_only":path.name,"source_sha256":h,
            "schema_status":"OLD_BINARY_FORMAT_NOT_PARSED_KEEP_ORIGINAL_SAFE_CONVERSION_NEEDED",
            "input_source_format":suffix.lstrip("."),
            "rows_eligible_for_study_accepted":0,"independent_DOBs_accepted":0,
            "bazi_variables_computed":0}, "alternatives":[]}
    raise RuntimeError("Unsupported source file format; need actual source type and schema")


def test_fixture()->None:
    fieldnames=["NOM","ENTREE","SUITE","DECES","DatNais","DatEntree","PaysNais","Etranger","Femme"]
    rows=[["Unexpected institutional banner"],fieldnames,
      ["A A","correspondant 1935","membre 1950","1970","21/02/1901","02/11/1935","France","0","0"],
      ["B B","membre 1942","","1972","00/00/0000","1942-03-11","France","0","1"],
      ["C C","associé étranger 1961","","1988","44023","1961-05-02","Germany","1","0"],
      ["D D","correspondant 1949","membre 1968","1980","31/02/1914","1949-07-13","France","0","0"]]
    report=inspect_rows(rows,origin="synthetic.csv",snapshot_sha="f"*64,source_format="csv")
    assert report["header_row_one_based"]==2
    assert report["nonempty_data_rows"]==4
    assert report["schema_status"]=="FIVE_CORE_FIELDS_DETECTED"
    q=report["field_nonempty_and_date_precision_counts"]
    assert q["DATNAIS_quality_day_precision_text_candidate"]==1
    assert q["DATNAIS_quality_explicit_unknown_sentinel"]==1
    assert q["DATNAIS_quality_numeric_excel_date_serial_or_number_REVIEW"]==1
    assert q["DATNAIS_quality_invalid_calendar_date"]==1

    # Minimal standardized XLSX fixture built in-memory for parser tests:
    # only XML shared strings, does not contain real people or source data.
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp)/"synthetic.xlsx"
        sheet_rows=[]
        for i,line in enumerate([fieldnames,["A A","correspondant 1900","membre 1950","","1901-02-21","1900-01-01","","0","0"]],1):
            vals=[]
            for j,v in enumerate(line):
                col=chr(ord("A")+j)
                escaped=(str(v).replace("&","&amp;").replace("<","&lt;"))
                vals.append(f'<c r="{col}{i}" t="inlineStr"><is><t>{escaped}</t></is></c>')
            sheet_rows.append(f'<row r="{i}">{"".join(vals)}</row>')
        ns=XLSX_NS
        with zipfile.ZipFile(p,"w") as z:
            z.writestr("xl/workbook.xml",f'<workbook xmlns="{ns}" xmlns:r="{REL_NS}"><sheets><sheet name="Master" sheetId="1" r:id="rId1"/></sheets></workbook>')
            z.writestr("xl/_rels/workbook.xml.rels",f'<Relationships xmlns="{PKG_NS}"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
            z.writestr("xl/worksheets/sheet1.xml",f'<worksheet xmlns="{ns}"><sheetData>{"".join(sheet_rows)}</sheetData></worksheet>')
        parsed=inspect_path(p)
        assert parsed["source_info"]["nonempty_data_rows"]==1
        assert parsed["source_info"]["schema_status"]=="FIVE_CORE_FIELDS_DETECTED"
        assert parsed["source_info"]["selected_sheet"]=="Master"

    assert month_date_quality("00/00/0000")=="explicit_unknown_sentinel"
    assert month_date_quality("13/13/1950")=="invalid_calendar_date"
    assert month_date_quality("18/06/1947")=="day_precision_text_candidate"
    print(json.dumps({
        "test":"leridon_source_schema_probe_synthetic_fixture_only",
        "synthetic_csv_header_test":"PASS",
        "synthetic_xlsx_ooxml_test":"PASS",
        "date_precision_guard_tests":"PASS",
        "real_3218_person_original_file_loaded":False,
        "network_requests":0,
        "bazi_variables_computed":0},ensure_ascii=False,indent=2))


def main()->int:
    p=argparse.ArgumentParser()
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument("--fixture-check",action="store_true")
    group.add_argument("--source",type=Path)
    p.add_argument("--out",type=Path,default=OUT)
    args=p.parse_args()
    if args.fixture_check:
        test_fixture()
        return 0
    try:
        result=inspect_path(args.source)
        report={
            "version":VERSION,"run_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
            "network_requests":0,"original_local_file_sha256":result["source_info"].get("source_sha256",""),
            "file_format":result["source_info"].get("input_source_format"),
            "source_audit":result["source_info"],
            "alternate_worksheets":result["alternatives"],
            "original_3218_person_index_independently_authenticated":False,
            "not_counting_membership_from_source_role_words":True,
            "accepted_DOB_count":0,"accepted_full_member_count":0,
            "bazi_variables_computed":0,
            "warning":"Schema and source field missingness only, NOT proof underlying file matches Leridon's publication or archived edition. Do not submit raw private person-level data by default."}
        args.out.mkdir(parents=True,exist_ok=True)
        (args.out/"summary.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps({"source_format":report["file_format"],"file_sha256":report["original_local_file_sha256"],
                          "audit":report["source_audit"]["schema_status"],
                          "source_rows":report["source_audit"].get("nonempty_data_rows"),
                          "found_columns":report["source_audit"].get("recognized_fields_and_columns_zero_based"),
                          "network_requests":0,"DOBs_accepted":0},ensure_ascii=False,indent=2))
        print("Share only local_runs summary.json; do not paste person-level file or full logs.")
    except Exception as exc:
        print("ERROR "+type(exc).__name__+": "+str(exc)[:340],file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    sys.exit(main())
