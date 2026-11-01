#!/usr/bin/env python3
"""Kiểm kê lại corpus cục bộ; không tự duyệt ngôn ngữ, bản dịch hoặc quyền sử dụng."""
from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data_pipeline.common import (describe, display_path, ensure_new, read_jsonl,
                                     run_report, sha256, text_pair, write_json)


def audit(data_dir: Path, registry_path: Path, output_dir: Path, snapshot_id: str,
          expected_inventory: Path | None = None, project_root: Path = ROOT) -> dict:
    destinations = [output_dir / name for name in ('inventory.json','source_registry.json','validation_report.json')]
    ensure_new(*destinations)
    prior = json.loads(registry_path.read_text(encoding='utf-8'))
    known = {item['path']: item for item in prior['sources']}
    files = sorted(p for layer in ('raw','interim','quarantine','processed','augmented')
                   for p in (data_dir / layer).rglob('*.jsonl'))
    files += sorted((data_dir / 'manifests').glob('*.log'))
    inventory, checks, sources = [], [], []
    duplicates = defaultdict(list)
    raw_count = 0
    raw_pair_count = 0
    for path in files:
        relative = display_path(path, project_root)
        signature = {'path':relative,'sha256':sha256(path),'bytes':path.stat().st_size}
        if path.suffix == '.log':
            inventory.append({**signature,'format':'text_log'})
            continue
        rows = read_jsonl(path)
        pairs = [text_pair(row) for row in rows]
        fields = defaultdict(Counter)
        for row in rows:
            for key, value in row.items():
                fields[key][type(value).__name__] += 1
        inventory.append({**signature,'format':'jsonl','records':len(rows),
                          'schema':{k:{'present':sum(v.values()),'types':dict(v)} for k,v in sorted(fields.items())}})
        normalized = [(a.casefold(),b.casefold()) for a,b in pairs if a or b]
        checks.append({**signature,'records':len(rows),'json_parse_errors':0,
                       'both_text_fields_present':sum(bool(a and b) for a,b in pairs),
                       'missing_source_url':sum(not r.get('source_url') for r in rows),
                       'duplicate_normalized_pairs':len(normalized)-len(set(normalized)),
                       'identical_normalized_sides':sum(bool(a and b) and a.casefold()==b.casefold() for a,b in pairs),
                       'claimed_review_status_counts':dict(Counter(str(r.get('review_status','not_recorded')) for r in rows)),
                       'filter_status_counts':dict(Counter(str(r.get('filter_status','not_recorded')) for r in rows))})
        if path.resolve().is_relative_to((data_dir/'raw').resolve()):
            raw_count += len(rows)
            raw_pair_count += sum(bool(a and b) for a,b in pairs)
            for number, (a,b) in enumerate(pairs,1):
                if a and b:
                    duplicates[(a.casefold(),b.casefold())].append({'path':relative,'record_number':number})
            previous = known.get(relative, {})
            same = previous.get('sha256') == signature['sha256']
            item = copy.deepcopy(previous) if same else {
                'source_id':path.parent.name, 'training_approved':False,
                'content_origin_status':'unverified', 'language_review_status':'pending',
                'translation_review_status':'pending', 'usage_permission_status':'not_confirmed',
            }
            item.update({**signature,'records':len(rows),'previous_registry_hash_matches':same,
                         'source_url_records':sum(bool(r.get('source_url')) for r in rows),
                         'claimed_source_domains':dict(Counter(str(r.get('source_domain','not_recorded')) for r in rows))})
            sources.append(item)
    comparisons = []
    if expected_inventory:
        expected = json.loads(expected_inventory.read_text(encoding='utf-8'))
        for item in expected['files']:
            path = (project_root / item['path']).resolve()
            if not path.is_relative_to(data_dir.resolve()):
                raise ValueError('Inventory tham chiếu file ngoài data_dir')
            comparisons.append({'path':item['path'], 'exists':path.is_file(),
                                'sha256_matches':path.is_file() and sha256(path)==item['sha256']})
    inputs = [registry_path] + ([expected_inventory] if expected_inventory else [])
    receipt = run_report('audit_data', inputs, [], snapshot_id=snapshot_id)
    summary = {'raw_files':len(sources),'raw_records':raw_count,
               'raw_records_with_both_text_fields':raw_pair_count,
               'registered_raw_files_missing':sorted(set(known)-{item['path'] for item in sources})}
    common = {'schema_version':2,'snapshot_id':snapshot_id,'created_at_utc':receipt['created_at_utc']}
    write_json(destinations[0], {**common,'summary':summary,'files':inventory,
               'record_count_note':'Do not sum records across processing stages or reproduction runs.'})
    write_json(destinations[1], {**common,'sources':sources,
               'scope':'Review decisions copied only for unchanged hashes; new/changed files reset to pending.',
               'supporting_assets':prior.get('supporting_assets',[])})
    report = {**common,'execution':receipt,'summary':summary,'files':checks,
              'snapshot_comparisons':comparisons,
              'raw_duplicate_pair_groups':[{'occurrences':refs} for refs in duplicates.values() if len(refs)>1],
              'normalization':'Unicode NFC, collapsed whitespace, casefold; files left unchanged',
              'not_performed':['External source verification','Linguistic/translation review','Permission verification',
                               'Near-duplicate detection','Train/validation/test leakage check'],
              'all_expected_hashes_match':all(item['sha256_matches'] for item in comparisons) if expected_inventory else None}
    write_json(destinations[2], report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,default=Path('data'))
    parser.add_argument('--registry',type=Path,default=Path('data/manifests/source_registry.json'))
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--snapshot-id',required=True)
    parser.add_argument('--expected-inventory',type=Path)
    args=parser.parse_args()
    report=audit(args.data_dir,args.registry,args.output_dir,args.snapshot_id,args.expected_inventory)
    print(json.dumps({'summary':report['summary'],'all_expected_hashes_match':report['all_expected_hashes_match']}))
    if report['all_expected_hashes_match'] is False:
        raise SystemExit(1)


if __name__=='__main__':
    main()
