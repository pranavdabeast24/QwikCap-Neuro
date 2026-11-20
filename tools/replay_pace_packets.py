"""Independent session replay of the owner-approved synthetic PACE packets.

The extractor receives forms only. Frozen expectations are read after extraction.
Automated confirmations exercise gates; they are not a clinical human review.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import io
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from desktop_model import DesktopSession
from verify_actual_pace_readout import build_expectations, canonical, cell_problem, read_json


def run(split, output, packet_name='sih-clinic-synthetic'):
    packet = ROOT / 'datasets' / packet_name
    forms = sorted((packet / split / 'forms').glob('*.pdf'))
    if not forms or any(path.is_symlink() or not path.is_file() for path in forms):
        raise ValueError('Use the unchanged synthetic packet included with the repository')
    if output.exists() or packet.resolve() == output.resolve() or packet.resolve() in output.resolve().parents:
        raise ValueError('Choose a new output directory outside the input packet')
    output.mkdir(parents=True)
    result = dict(packet=packet_name, split=split, regressionOnly=True, sourceDocuments=len(forms),
                  automatedSyntheticConfirmations=True, humanClinicalReview=False,
                  manualValueEdits=0, answerKeysPassedToApp=False)
    session = DesktopSession()
    try:
        session.use_pace_auto_profile()
        imported = session.import_pace_documents(forms)
        groups = imported['groups']
        result['proposedPatients'] = len(groups)
        result['importFailures'] = imported.get('failed', [])
        result['groupIssues'] = [issue for group in groups for issue in group.get('issues', [])]
        assert len(groups) == 5, 'Expected exactly five synthetic patient groups'
        assert sum(group['sourceCount'] for group in groups) == len(forms)
        assert not result['importFailures'] and not result['groupIssues']
        committed = session.confirm_pace_groups([group['id'] for group in groups], confirmed_identity=True)
        result['commitFailures'] = committed.get('failed', [])
        state = session.snapshot()
        assert not result['commitFailures'] and len(state['records']) == 5
        assert len(state['schema']) == 512
        initial = {record['values']['mrn']: dict(record['values']) for record in state['records']}
        assert len(initial) == 5
        ids = {values['record_id'] for values in initial.values()}
        assert len(ids) == 5 and not ids & set(initial)

        # This comparison uses only the frozen independent answer-key artifacts.
        expected_file = packet / 'evaluation' / ('test-expected-comparator.json' if split == 'test' else 'train-expected.json')
        result['expectationPolicy'] = 'Frozen wildcard-expanded test comparator' if split == 'test' else 'Frozen original train keys'
        expected = build_expectations(read_json(expected_file), read_json(ROOT / 'study_profiles/pace.json'),
                                      read_json(packet / 'evaluation' / f'{split}-form-census.json'))
        expected_by_mrn = {values['mrn']: record_id for record_id, values in expected.patients.items()}
        assert set(expected_by_mrn) == set(initial), 'Patient grouping differs from independent key identities'
        differences = []
        checked = 0
        for mrn, actual in initial.items():
            key_id = expected_by_mrn[mrn]
            for name in expected.columns:
                if name == 'record_id':
                    continue
                checked += 1
                problem = cell_problem(actual[name], expected.patients[key_id][name], expected.fields[name])
                if problem:
                    differences.append(dict(patientIndex=list(initial).index(mrn) + 1, field=name, reason=problem))
        result.update(fullGridExcludingTemporaryId=dict(checked=checked, matched=checked-len(differences),
                                                      differences=differences),
                      expectationSHA256=hashlib.sha256(expected_file.read_bytes()).hexdigest())
        approvals = []
        for record in state['records']:
            try:
                session.review_record(record['id'], record['values'], record['applicableFields'],
                                      reviewer='Automated synthetic regression', approve=True,
                                      expected_revision=record['revision'])
                approvals.append(True)
            except Exception as exc:
                approvals.append(False)
                result.setdefault('approvalErrors', []).append(str(exc))
        result['approvedPatients'] = sum(approvals)
        assert all(approvals), 'Source/review gates did not accept the supplied synthetic groups'
        session.use_categories_as_columns()
        state = session.snapshot()
        session.set_mapping({field['name']: field['name'] for field in state['schema']}, confirmed=True,
                            expected_revision=state['template']['revision'])
        for kind in ('csv', 'xlsx'):
            revision = session.snapshot()['template']['revision']
            data = session.export(kind, output / f'{packet_name}-{split}-auto.{kind}', expected_revision=revision)
            if kind == 'csv':
                rows = list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))
                assert len(rows) == 5 and all(len(row) == 512 for row in rows)
                assert {row['mrn']: row for row in rows} == initial
            else:
                from openpyxl import load_workbook
                workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=False)
                try:
                    sheet = workbook.active
                    cells = list(sheet.iter_rows())
                    columns = [cell.value for cell in cells[0]]
                    assert columns == [field['name'] for field in state['schema']]
                    assert len(cells) == 6 and all(len(row) == 512 for row in cells)
                    rows = [dict(zip(columns, ['' if cell.value is None else str(cell.value) for cell in row])) for row in cells[1:]]
                    assert {row['mrn'] for row in rows} == set(initial)
                    for row, values in zip(cells[1:], rows):
                        for name, cell in zip(columns, row):
                            field = expected.fields[name]
                            assert cell_problem(cell.value, canonical(initial[values['mrn']][name], field), field,
                                                excel=True, data_type=cell.data_type) is None, name
                        assert row[columns.index('mrn')].data_type == 's'
                        assert row[columns.index('record_id')].data_type == 's'
                finally:
                    workbook.close()
            result[f'{kind}SHA256'] = hashlib.sha256(data).hexdigest()
        project = output / f'{packet_name}-{split}-auto.json'
        session.save_project(project)
        session.open_project(project)
        reopened = session.snapshot()
        assert {r['values']['mrn']: r['values']['record_id'] for r in reopened['records']} == {
            mrn: values['record_id'] for mrn, values in initial.items()}
        assert all(r['status'] != 'approved' and not r['confirmed'] for r in reopened['records'])
        result['temporaryIdsStableAfterReopen'] = True
        result['exportedPatientRows'] = 5
        result['headers'] = 512
        result['workflowPassed'] = True
    except Exception as exc:
        result.update(workflowPassed=False, error=str(exc))
        raise
    finally:
        session.close()
        (output / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps({key:value for key,value in result.items() if key != 'fullGridExcludingTemporaryId'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--split', choices=['train','test'], required=True)
    parser.add_argument('--packet', choices=['sih-clinic-synthetic','sih-synthetic'], default='sih-clinic-synthetic')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.split, args.output, args.packet)
