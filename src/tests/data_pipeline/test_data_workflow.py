from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.data_pipeline.audit_data import audit
from src.data_pipeline.clean_dedup import process_all_raw_data
from src.data_pipeline.common import ROOT, read_jsonl, sha256, write_json, write_jsonl
from src.data_pipeline.crawl_vov4 import VovArticleParser, crawl
from src.data_pipeline.split_dataset import connected_groups, split_dataset


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.raw = self.root/'data/raw/sample/rows.jsonl'
        self.registry = self.root/'data/manifests/source_registry.json'
        self.output = self.root/'data/processed/clean.jsonl'
        self.clean_report = self.root/'data/manifests/clean.json'
        self.rows = [{'tay_text':f'Tày {i}', 'vi_text':f'Việt {i}',
                      'source_doc_id':f'doc{i}', 'review_status':'gold_standard'} for i in range(12)]

    def prepare(self, approved=False, rows=None):
        self.rows = self.rows if rows is None else rows
        write_jsonl(self.raw, self.rows)
        source = {'source_id':'sample','path':'data/raw/sample/rows.jsonl',
                  'sha256':sha256(self.raw),'training_approved':approved}
        if approved:
            source.update({'content_origin_status':'verified','language_review_status':'approved',
                           'translation_review_status':'approved','usage_permission_status':'confirmed',
                           'reviewed_by':'fixture reviewer','review_evidence':['fixture only'],
                           'approved_record_numbers':list(range(1,len(self.rows)+1))})
        write_json(self.registry, {'sources':[source]})
        return source

    def clean(self):
        return process_all_raw_data(self.root/'data/raw', self.output, self.registry,
                                    self.clean_report, self.root)

    def edit_registry(self, update):
        data=json.loads(self.registry.read_text())
        update(data['sources'][0])
        self.registry.write_text(json.dumps(data))

    def test_unverified_gold_label_does_not_create_processed(self):
        self.prepare()
        report=self.clean()
        self.assertEqual(report['status'],'no_approved_data')
        self.assertFalse(self.output.parent.exists())
        self.assertEqual(report['approved_records'],0)

    def test_boolean_approval_alone_is_insufficient(self):
        self.prepare()
        self.edit_registry(lambda s:s.update(training_approved=True))
        with self.assertRaises(ValueError): self.clean()
        self.assertFalse(self.output.exists())

    def test_changed_raw_invalidates_approval(self):
        self.prepare(True)
        self.raw.write_text(self.raw.read_text()+'\n')
        with self.assertRaisesRegex(ValueError,'Checksum'): self.clean()

    def test_unregistered_input_is_not_silently_included(self):
        self.prepare(True)
        write_jsonl(self.raw.parent/'extra.jsonl',self.rows)
        with self.assertRaisesRegex(ValueError,'chưa được khai báo'): self.clean()

    def test_record_selection_normalization_dedup_and_provenance(self):
        rows=[{'tay_text':'  Ta\u0300y  A ', 'vi_text':' Việt A ', 'source_doc_id':'doc-a'},
              {'tay_text':'Tày A','vi_text':'Việt A','source_doc_id':'doc-b'},
              {'tay_text':'Không duyệt','vi_text':'Excluded','source_doc_id':'doc-c'}]
        self.prepare(True,rows)
        self.edit_registry(lambda s:s.update(approved_record_numbers=[1,2]))
        report=self.clean()
        self.assertEqual(report['kept_pairs'],1)
        row=read_jsonl(self.output)[0]
        self.assertEqual(row['tay_text'],'Tày A')
        self.assertEqual(len(row['source_records']),2)
        self.assertEqual(row['source_documents'],['sample:doc-a','sample:doc-b'])

    def test_no_silent_monolingual_autoencoder(self):
        self.prepare(True,[{'tay_text':'Tày','source_doc_id':'d'}])
        with self.assertRaisesRegex(ValueError,'thiếu một phía'): self.clean()
        self.assertFalse(self.output.exists())

    def test_approved_record_number_bounds(self):
        self.prepare(True)
        self.edit_registry(lambda s:s.update(approved_record_numbers=[999]))
        with self.assertRaisesRegex(ValueError,'approved_record_numbers'): self.clean()

    def test_existing_output_is_preserved(self):
        self.prepare(True)
        self.output.parent.mkdir(parents=True)
        self.output.write_text('keep me')
        with self.assertRaises(FileExistsError): self.clean()
        self.assertEqual(self.output.read_text(),'keep me')

    def test_split_groups_shared_sides_transitively(self):
        rows=[{'tay_text':a,'vi_text':b,'source_documents':[d],'training_approved':True}
              for a,b,d in [('a','x','d1'),('a','y','d2'),('b','y','d3'),('c','z','d4')]]
        groups=connected_groups(rows)
        self.assertEqual(sorted(map(len,groups)),[1,3])

    def test_split_is_deterministic_and_disjoint(self):
        self.prepare(True)
        self.clean()
        for suffix in ['a','b']:
            split_dataset(self.output,self.root/suffix,self.clean_report,self.root/(suffix+'.json'))
        for name in ['train_e0.jsonl','val.jsonl','test.jsonl']:
            self.assertEqual((self.root/'a'/name).read_bytes(),(self.root/'b'/name).read_bytes())
        splits=[read_jsonl(self.root/'a'/n) for n in ['train_e0.jsonl','val.jsonl','test.jsonl']]
        for i in range(3):
            for j in range(i+1,3):
                for field in ['tay_text','vi_text']:
                    self.assertFalse({r[field] for r in splits[i]} & {r[field] for r in splits[j]})
                self.assertFalse({d for r in splits[i] for d in r['source_documents']} &
                                 {d for r in splits[j] for d in r['source_documents']})

    def test_split_rejects_stale_cleaned_data(self):
        self.prepare(True)
        self.clean()
        self.output.write_text(self.output.read_text()+'\n')
        with self.assertRaisesRegex(ValueError,'checksum'):
            split_dataset(self.output,self.root/'split',self.clean_report,self.root/'split.json')
        self.assertFalse((self.root/'split').exists())

    def test_split_refuses_invalid_ratios(self):
        with self.assertRaises(ValueError):
            split_dataset(self.output,self.root/'split',self.clean_report,self.root/'split.json',.9,.2)

    def test_split_refuses_fewer_than_three_independent_groups(self):
        self.prepare(True,self.rows[:2])
        self.clean()
        with self.assertRaisesRegex(ValueError,'3 nhóm'):
            split_dataset(self.output,self.root/'split',self.clean_report,self.root/'split.json')
        self.assertFalse((self.root/'split').exists())

    def test_audit_preserves_only_unchanged_review_decisions(self):
        self.prepare(True)
        report=audit(self.root/'data',self.registry,self.root/'audit1','test1',project_root=self.root)
        updated=json.loads((self.root/'audit1/source_registry.json').read_text())
        self.assertTrue(updated['sources'][0]['training_approved'])
        self.assertEqual(report['summary']['raw_records'],12)
        self.raw.write_text(self.raw.read_text()+'\n')
        audit(self.root/'data',self.registry,self.root/'audit2','test2',project_root=self.root)
        updated=json.loads((self.root/'audit2/source_registry.json').read_text())
        self.assertFalse(updated['sources'][0]['training_approved'])
        self.assertNotIn('approved_record_numbers',updated['sources'][0])

    def test_audit_detects_missing_snapshot_file(self):
        self.prepare()
        expected=self.root/'expected.json'
        write_json(expected,{'files':[{'path':'data/raw/missing.jsonl','sha256':'wrong'}]})
        result=audit(self.root/'data',self.registry,self.root/'audit','test',expected,self.root)
        self.assertFalse(result['all_expected_hashes_match'])

    def test_jsonl_rejects_non_object(self):
        self.raw.parent.mkdir(parents=True)
        self.raw.write_text('[]\n')
        with self.assertRaisesRegex(ValueError,'object'): read_jsonl(self.raw)

    def test_candidate_cli_does_not_overwrite(self):
        self.prepare()
        out=self.root/'candidate.jsonl'; out.write_text('untouched')
        result=subprocess.run([sys.executable,str(ROOT/'src/data_pipeline/build_vov_candidates.py'),
                               '--input',str(self.raw),'--output',str(out),
                               '--manifest',str(self.root/'run.json')],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(out.read_text(),'untouched')


class CrawlerTests(unittest.TestCase):
    def test_invalid_scope_fails_before_network(self):
        with patch('src.data_pipeline.crawl_vov4.load_robots') as robots:
            with self.assertRaises(ValueError): crawl('https://example.com',1,1,10)
            robots.assert_not_called()

    def test_robots_denial_stops_fetch(self):
        with patch('src.data_pipeline.crawl_vov4.load_robots') as robots, \
             patch('src.data_pipeline.crawl_vov4.fetch_text') as fetch:
            robots.return_value.can_fetch.return_value=False
            with self.assertRaises(RuntimeError): crawl('https://vov4.vov.vn/taynung',1,1,10)
            fetch.assert_not_called()

    def test_parser_keeps_uncertain_language_and_license(self):
        parser=VovArticleParser()
        parser.feed('<html lang="taynung"><meta property="og:title" content="Tiêu đề">'
                    '<meta property="og:description" content="Nội dung">'
                    '<article><div class="text-long"><p>Văn bản</p></div></article></html>')
        row=parser.article('https://vov4.vov.vn/taynung/example.vov4')
        self.assertEqual(row['body_blocks'],['Văn bản'])
        self.assertEqual(row['license_status'],'permission_required')
        self.assertEqual(row['language_label'],'unverified_tay_nung')


if __name__=='__main__':
    unittest.main()
