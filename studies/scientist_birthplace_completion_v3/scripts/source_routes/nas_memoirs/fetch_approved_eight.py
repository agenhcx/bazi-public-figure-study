import datetime
import hashlib
import json
import os
import pathlib
import urllib.error
import urllib.request

BASE = pathlib.Path(__file__).resolve().parents[1]
LEDGER = BASE / 'retained/request_ledger.jsonl'
CHAPTERS = [4, 7, 11, 14, 15, 17, 18, 20]


def append(event):
    event['utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with LEDGER.open('a') as f:
        f.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + '\n')
        f.flush()
        os.fsync(f.fileno())


def main():
    observed_index = (BASE / 'raw/nas_memoirs_nav_05.html').read_text()
    append({'event': 'authorization', 'scope': 'parent explicitly approved only eight observed Volume72 chapter URLs once each; no runtime/API/index expansion', 'chapters': CHAPTERS})
    failures = {}
    for chapter in CHAPTERS:
        request_id = f'nas_memoirs_chapter_{chapter:02d}'
        url = f'https://www.nationalacademies.org/read/5859/chapter/{chapter}'
        assert url + '"' in observed_index or url + "'" in observed_index
        assert not (BASE / f'raw/{request_id}.html').exists()
        append({'event': 'intent', 'request_id': request_id, 'kind': 'approved_independently_authored_memoir_full_body', 'url': url, 'attempt': 1, 'retry_allowed': False, 'source_grade_if_valid': 'S2_edited_signed_biographical_memoir'})
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=15) as response:
                body = response.read()
                status = response.status
                final_url = response.url
            path = BASE / f'raw/{request_id}.html'
            path.write_bytes(body)
            append({'event': 'result', 'request_id': request_id, 'http_status': status, 'url': url, 'final_url': final_url, 'raw_source_file': str(path.relative_to(BASE.parents[1])), 'original_bytes_sha256': hashlib.sha256(body).hexdigest(), 'capture_kind': 'original_HTTP_response_body', 'capture_scope': 'complete observed memoir chapter HTML response; no subresources requested', 'bytes': len(body)})
            print(json.dumps({'request_id': request_id, 'status': status, 'bytes': len(body)}), flush=True)
        except Exception as exc:
            status = exc.code if isinstance(exc, urllib.error.HTTPError) else None
            append({'event': 'result', 'request_id': request_id, 'url': url, 'http_status': status, 'error_type': type(exc).__name__, 'error': str(exc), 'capture_kind': 'fetch_error_no_body'})
            print(json.dumps({'request_id': request_id, 'status': status, 'error': str(exc)}), flush=True)
            if status in [403, 503]:
                failures[status] = failures.get(status, 0) + 1
            if status == 429 or failures.get(status, 0) >= 2:
                append({'event': 'stop', 'reason': f'HTTP{status} stop threshold reached', 'request_id': request_id})
                break


if __name__ == '__main__':
    main()
