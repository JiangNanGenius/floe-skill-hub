#!/usr/bin/env python3
"""Check DOI registration and retrieve Crossref metadata for manual citation review.

Adapted for Floe from the upstream MIT script (K-Dense scientific-agent-skills
593377bb, skills/literature-review/scripts/verify_citations.py); the DOI
taxonomy, retry discipline and honesty rules are preserved. Floe changes:

* `requests` is replaced by the Python standard library (`urllib.request`),
  so this script has NO third-party dependency — it runs on the bare guest
  interpreter.
* NEW `--offline-dir` mode: verify against Crossref/Handle records the agent
  already fetched into the task workspace with the NATIVE `web.fetch` /
  `network.http` tools (the preferred Floe path — no guest network egress
  needed). Each record file is `<percent-encoded-doi>.json` containing
  {"handle_response": {...}} and/or {"crossref_works": {...}} — the raw JSON
  bodies of https://doi.org/api/handles/<doi> and
  https://api.crossref.org/works/<doi>.
* The report records the mode; offline verification never claims more than
  the fetched records show, and a missing offline record is inconclusive,
  not registered.

Registration does not establish that a citation supports a claim. Crossref
does not cover all DOI registration agencies; unavailable metadata needs
manual review. Nothing here fabricates fields: only values present in the
retrieved record are reported.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import quote, unquote

USER_AGENT = "FloeLiteratureReviewCitationVerifier/1.0 (skill literature-review 1.0.0)"
TIMEOUT_SECONDS = 20
REPORT_SCOPE = ("DOI registration and Crossref metadata, not claim support "
                "or retraction screening")


def normalize_doi(value: str) -> str:
    """Normalize a bare DOI or doi.org URL without stripping legal DOI punctuation."""
    value = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", value.strip(), flags=re.I)
    return unquote(value).lower()


def extract_dois(text: str) -> List[str]:
    """Extract unique candidates; prose punctuation remains inherently ambiguous."""
    found: List[str] = []
    for candidate in re.findall(r'10\.\d{4,9}/[^\s<>"{}]+', text, flags=re.I):
        candidate = unquote(candidate).rstrip('.,;:')
        # Keep balanced parentheses inside older DOI suffixes, remove Markdown closers.
        while candidate and candidate[-1] in ')]':
            closing = candidate[-1]
            opening = '(' if closing == ')' else '['
            if candidate.count(closing) <= candidate.count(opening):
                break
            candidate = candidate[:-1].rstrip('.,;:')
        normalized = normalize_doi(candidate)
        if normalized and normalized not in found:
            found.append(normalized)
    return found


def valid_doi_syntax(doi: str) -> bool:
    return bool(re.fullmatch(r'10\.\d{4,9}/\S+', doi))


def format_authors(authors: Any) -> str:
    """Preserve all authors for review; this is not a CSL citation formatter."""
    names = []
    for author in authors if isinstance(authors, list) else []:
        if not isinstance(author, dict):
            continue
        family, given = author.get('family', ''), author.get('given', '')
        if family:
            names.append(f'{family}, {given}' if given else family)
        elif author.get('name'):
            names.append(author['name'])
    return '; '.join(names)


def extract_year(message: Dict) -> str:
    for field in ('published-print', 'published-online', 'published', 'issued'):
        dates = ((message.get(field) or {}).get('date-parts') or []) if isinstance(message, dict) else []
        if dates and dates[0]:
            return str(dates[0][0])
    return ''


def classify_handle(payload: Any, doi: str) -> str:
    """Return 'registered' | 'missing' | 'inconclusive' from a Handle API body."""
    if not isinstance(payload, dict):
        return 'inconclusive'
    code = payload.get('responseCode')
    returned = payload.get('handle', '')
    if code == 100:
        return 'missing'
    if code == 1 and isinstance(returned, str) and normalize_doi(returned) == doi:
        return 'registered'
    return 'inconclusive'


def summarize_crossref(message: Any, doi: str) -> Dict:
    """Map a Crossref works 'message' object to review metadata (no invention)."""
    if not isinstance(message, dict) or normalize_doi(str(message.get('DOI', ''))) != doi:
        return {'metadata_status': 'unavailable',
                'error': 'Crossref response DOI missing or mismatched'}

    def first(field):
        values = message.get(field) or []
        return values[0] if isinstance(values, list) and values else ''

    authors = message.get('author') or []
    return {
        'metadata_status': 'retrieved', 'title': first('title'),
        'authors': format_authors(authors), 'author': authors,
        'year': extract_year(message), 'journal': first('container-title'),
        'volume': message.get('volume', ''), 'issue': message.get('issue', ''),
        'pages': message.get('page', ''), 'doi': doi,
        'crossref_message': message,
    }


class CitationVerifier:
    """Online (stdlib urllib) or offline (agent-fetched records) DOI checking."""

    def __init__(self, email: str | None = None, offline_dir: Path | None = None):
        self.email = email
        self.offline_dir = offline_dir
        self.mode = 'offline' if offline_dir is not None else 'online'

    # -- online transport (stdlib only) ------------------------------------
    def _get(self, url: str, params: Dict | None = None) -> Tuple[int, Any]:
        """Bounded-retry GET; returns (status, parsed-json-or-None)."""
        if params:
            url = url + ('&' if '?' in url else '?') + urllib.parse.urlencode(params)
        last_status = 0
        for attempt in range(3):
            request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT,
                                                           'Accept': 'application/json'})
            try:
                with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                    body = response.read()
                    last_status = response.status
                    try:
                        return response.status, json.loads(body)
                    except json.JSONDecodeError:
                        return response.status, None
            except urllib.error.HTTPError as exc:
                last_status = exc.code
                if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                    try:
                        payload = json.loads(exc.read())
                    except Exception:
                        payload = None
                    return exc.code, payload
                delay_header = exc.headers.get('Retry-After') if exc.headers else None
                try:
                    delay = float(delay_header) if delay_header else 2 ** attempt
                except (TypeError, ValueError):
                    delay = 2 ** attempt
                if delay > 60:      # server-directed long delay: later run, not retry
                    return exc.code, None
                time.sleep(max(0.0, delay))
            except (urllib.error.URLError, OSError, ValueError):
                if attempt == 2:
                    return 0, None
                time.sleep(2 ** attempt)
        return last_status, None

    # -- offline transport --------------------------------------------------
    def _load_offline(self, doi: str) -> Dict:
        path = self.offline_dir / (quote(doi, safe='') + '.json')
        if not path.is_file():
            return {'offline_record': 'missing'}
        try:
            record = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            return {'offline_record': 'unreadable'}
        return record if isinstance(record, dict) else {'offline_record': 'malformed'}

    # -- verification --------------------------------------------------------
    def verify_doi(self, doi: str) -> Tuple[bool, Dict]:
        """Return registration status and metadata; false includes inconclusive."""
        doi = normalize_doi(doi)
        if not valid_doi_syntax(doi):
            return False, {'doi': doi, 'status': 'invalid_syntax'}
        if self.mode == 'offline':
            record = self._load_offline(doi)
            if 'offline_record' in record:
                return False, {'doi': doi, 'status': 'inconclusive',
                               'offline_record': record['offline_record'],
                               'note': 'offline verification cannot claim registration without a fetched record'}
            handle_status = classify_handle(record.get('handle_response'), doi)
            if handle_status != 'registered':
                return False, {'doi': doi, 'status': handle_status,
                               'handle_response': record.get('handle_response')}
            metadata = summarize_crossref((record.get('crossref_works') or {}).get('message')
                                          if isinstance(record.get('crossref_works'), dict) else None,
                                          doi)
            if metadata.get('metadata_status') != 'retrieved':
                metadata = {'metadata_status': 'unavailable',
                            'note': 'handle registered; no usable Crossref record was fetched'}
            metadata.update({'doi': doi, 'status': 'registered', 'mode': 'offline'})
            return True, metadata
        # online mode
        try:
            status, payload = self._get(f"https://doi.org/api/handles/{quote(doi, safe='/')}")
            handle_status = classify_handle(payload, doi)
            if handle_status == 'missing':
                return False, {'doi': doi, 'status': 'missing',
                               'handle_response_code': (payload or {}).get('responseCode')
                               if isinstance(payload, dict) else None}
            if handle_status != 'registered':
                return False, {'doi': doi, 'status': 'inconclusive', 'http_status': status}
            metadata = self._crossref_metadata(doi)
            metadata.update({'doi': doi, 'status': 'registered', 'mode': 'online'})
            return True, metadata
        except (urllib.error.URLError, OSError, ValueError) as exc:
            return False, {'doi': doi, 'status': 'inconclusive', 'error': str(exc)}

    def _crossref_metadata(self, doi: str) -> Dict:
        params = {'mailto': self.email} if self.email else None
        status, payload = self._get(f"https://api.crossref.org/works/{quote(doi, safe='/')}", params)
        if status != 200 or not isinstance(payload, dict):
            return {'metadata_status': 'unavailable', 'crossref_http_status': status}
        return summarize_crossref(payload.get('message'), doi)

    def verify_url(self, url: str) -> Tuple[bool, int]:
        """Check accessibility only; a 403/HEAD failure is not proof of an invalid URL."""
        if self.mode == 'offline':
            return False, 0
        request = urllib.request.Request(url, method='HEAD', headers={'User-Agent': USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                return response.status < 400, response.status
        except urllib.error.HTTPError as exc:
            return exc.code < 400, exc.code
        except (urllib.error.URLError, OSError, ValueError):
            return False, 0

    def verify_citations_in_file(self, filepath: str, *, throttle: bool = True) -> Dict:
        dois = extract_dois(Path(filepath).read_text(encoding='utf-8'))
        report: Dict[str, Any] = {
            'mode': self.mode,
            'total_dois': len(dois),
            'verified': [], 'failed': [], 'metadata_unavailable': [],
            'metadata': {}, 'errors': {}, 'missing': [], 'inconclusive': [],
            'invalid_syntax': [],
            'verification_scope': REPORT_SCOPE,
        }
        for index, doi in enumerate(dois):
            print(f'Checking DOI: {doi}')
            registered, metadata = self.verify_doi(doi)
            if registered:
                report['verified'].append(doi)
                report['metadata'][doi] = metadata
                if metadata.get('metadata_status') != 'retrieved':
                    report['metadata_unavailable'].append(doi)
            else:
                report['failed'].append(doi)
                report['errors'][doi] = metadata
                status = metadata.get('status')
                if status == 'missing':
                    report['missing'].append(doi)
                elif status == 'invalid_syntax':
                    report['invalid_syntax'].append(doi)
                else:
                    report['inconclusive'].append(doi)
            if throttle and self.mode == 'online' and index + 1 < len(dois):
                time.sleep(0.5)  # sequential, <=2 Crossref single-work requests/s
        return report


def format_citation_apa(metadata: Dict) -> str:
    """Return a metadata preview, not a standards-compliant APA reference."""
    return (f"{metadata.get('authors', '')} ({metadata.get('year') or 'n.d.'}). "
            f"{metadata.get('title', '')}. {metadata.get('journal', '')}. "
            f"https://doi.org/{metadata.get('doi', '')}")


def format_citation_nature(metadata: Dict) -> str:
    """Return a metadata preview; use CSL for final Nature formatting."""
    return (f"{metadata.get('authors', '')} {metadata.get('title', '')}. "
            f"{metadata.get('journal', '')} {metadata.get('volume', '')}, "
            f"{metadata.get('pages', '')} ({metadata.get('year', '')}).")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('markdown_file', type=Path)
    parser.add_argument('--email', help='contact email for the Crossref polite pool (online mode)')
    parser.add_argument('--offline-dir', type=Path,
                        help='directory of agent-fetched <percent-encoded-doi>.json records '
                             '(web.fetch/network.http); no guest network egress is used')
    parser.add_argument('-o', '--output', type=Path, help='JSON report path')
    args = parser.parse_args(argv)
    output = args.output or args.markdown_file.with_name(args.markdown_file.stem + '_citation_report.json')
    try:
        if output.resolve() == args.markdown_file.resolve():
            parser.error('report path must differ from the input file')
        offline_dir = None
        if args.offline_dir is not None:
            offline_dir = args.offline_dir.resolve(strict=True)
            if not offline_dir.is_dir():
                parser.error('--offline-dir must be an existing directory')
        verifier = CitationVerifier(email=args.email, offline_dir=offline_dir)
        report = verifier.verify_citations_in_file(str(args.markdown_file))
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    except (OSError, ValueError) as exc:
        parser.exit(1, f'[FAIL] {exc}\n')
    print(f"Mode: {report['mode']}; registered: {len(report['verified'])}; "
          f"unresolved: {len(report['failed'])}; "
          f"metadata unavailable: {len(report['metadata_unavailable'])}")
    print(f'[OK] Report: {output}')
    if not report['total_dois']:
        print('[WARN] No DOIs found; review references manually.')
    raise SystemExit(1 if report['failed'] else 0)


if __name__ == '__main__':
    raise SystemExit(main())
