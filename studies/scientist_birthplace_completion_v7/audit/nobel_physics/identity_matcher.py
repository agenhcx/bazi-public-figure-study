"""Offline name comparison only. Full API name is authoritative for acceptance.
No QIDs, DOB adoption, cross-cohort identity updates, or geography are performed.
Use route_name_aliases for discovery/holds; require full_name_matches AND exact
native/source dates AND bidirectional uniqueness for any accepted fact.
"""
import re,unicodedata
SUFFIXES={'jr','sr','ii','iii','iv'}
def parts(name):
    return [x for x in re.findall('[a-z]+',unicodedata.normalize('NFKD',name).encode('ascii','ignore').decode().lower()) if x not in SUFFIXES]
def name_aliases(source):
    out=[]
    for field in ['fullName','knownName']:
        n=source.get(field,{}).get('en')
        if n and n not in [x['value'] for x in out]:out.append({'field':field+'.en','value':n})
    n=' '.join(x for x in [source.get('givenName',{}).get('en'),source.get('familyName',{}).get('en')] if x)
    if n and n not in [x['value'] for x in out]:out.append({'field':'givenName.en + familyName.en','value':n})
    return out

def compatible(native,source_name,family_name,allow_source_initial_for_native_full=False):
    a,b,f=parts(native),parts(source_name),parts(family_name)
    if not a or not b or not f or len(a)<=len(f) or len(b)<=len(f):return False
    if a[-len(f):]!=f or b[-len(f):]!=f:return False
    aa,bb=a[:-len(f)],b[:-len(f)]
    def token_ok(native_part,source_part):
        return native_part==source_part or len(native_part)==1 and source_part.startswith(native_part) or allow_source_initial_for_native_full and len(source_part)==1 and native_part.startswith(source_part)
    if not token_ok(aa[0],bb[0]):return False
    pos=0
    for token in aa:
        while pos<len(bb) and not token_ok(token,bb[pos]):pos+=1
        if pos==len(bb):return False
        pos+=1
    return True

def full_name_matches(native,source):
    """Require every known native full token in API fullName; initial-only source
    cannot prove a longer known native token. KnownName cannot override this."""
    name=source.get('fullName',{}).get('en','');family=source.get('familyName',{}).get('en','')
    return [{'field':'fullName.en','value':name}] if name and compatible(native,name,family,False) else []

def route_name_aliases(native,source):
    """Permissive routing only; results MUST NOT be accepted without strict review."""
    family=source.get('familyName',{}).get('en','')
    return [a for a in name_aliases(source) if compatible(native,a['value'],family,True)]
