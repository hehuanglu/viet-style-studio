#!/usr/bin/env python3
"""Recompute quote, rubric, balanced total, and candidate-link checks from a saved VP v2 job.

Usage from repository root:
  python3 docs/viet-phuc-v2/prompt-refinement-20261010/round1/objective_crosscheck.py \
    SNAPSHOT.json OUTPUT.json

The snapshot and config are read only. Only OUTPUT.json is written.
"""
import argparse
import json
import math
from pathlib import Path


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def weighted_score(ratings, rubric):
    numerator = denominator = 0.0
    unknown = []
    invalid = []
    for row in ratings or []:
        cid = row.get('criterion_id')
        value = row.get('rating')
        if not finite(value):
            invalid.append({'criterion_id': cid, 'value': repr(value)})
            continue
        weight = rubric.get(cid)
        if row.get('applicable') and weight is not None:
            numerator += weight * value / 5
            denominator += weight
        elif row.get('applicable') and weight is None:
            unknown.append(cid)
    return (round(100 * numerator / denominator, 2) if denominator else None), unknown, invalid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--config', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[4]
    config_path = args.config or root / 'backend/viet_phuc/config.json'
    job = json.loads(args.snapshot.read_text())
    config = json.loads(config_path.read_text())
    profile = job.get('scoring_profile')
    weights = config['profiles'].get(profile, {})
    candidates = {c['candidate_id']: c for c in job.get('prompt_pool', []) if c.get('candidate_id')}
    rows, quote_issues, specialist_mismatches = [], [], []
    harmony_mismatches, total_mismatches, link_issues, nonfinite = [], [], [], []

    for candidate_id, candidate in candidates.items():
        specialists = job.get('specialist_audits', {}).get(candidate_id, {})
        reported_scores, calculated_scores, specialist_match = {}, {}, {}
        for role in ('fashion', 'culture', 'art'):
            audit = specialists.get(role)
            if not audit:
                link_issues.append({'candidate_id': candidate_id, 'problem': f'missing {role} audit'})
                continue
            if (audit.get('candidate_id'), audit.get('candidate_revision'), audit.get('content_hash')) != (
                candidate_id, candidate.get('revision'), candidate.get('content_hash')
            ):
                link_issues.append({'candidate_id': candidate_id, 'problem': f'{role} audit ID/revision/hash mismatch'})
            reported_scores[role] = audit.get('score')
            if audit.get('score') is not None and not finite(audit.get('score')):
                nonfinite.append({'candidate_id': candidate_id, 'field': f'{role}.score', 'value': repr(audit.get('score'))})
            calculated, unknown, invalid = weighted_score(audit.get('criterion_ratings'), config['rubrics'][role])
            calculated_scores[role] = calculated
            specialist_match[role] = calculated == audit.get('score')
            if calculated != audit.get('score'):
                specialist_mismatches.append({'candidate_id': candidate_id, 'role': role,
                                              'reported': audit.get('score'), 'rubric_calculated': calculated})
            if unknown:
                link_issues.append({'candidate_id': candidate_id, 'problem': f'{role} has unknown applicable rubric IDs', 'criterion_ids': unknown})
            nonfinite.extend({'candidate_id': candidate_id, 'role': role, **item} for item in invalid)
            if audit.get('score') is not None and not finite(audit.get('score')):
                nonfinite.append({'candidate_id': candidate_id, 'field': f'{role}.score', 'value': repr(audit.get('score'))})
            for check in audit.get('checks', []):
                quote = check.get('prompt_quote')
                if quote and quote not in candidate.get('image_prompt', ''):
                    quote_issues.append({'candidate_id': candidate_id, 'role': role,
                                         'check_id': check.get('check_id'), 'quote': quote,
                                         'quote_is_prompt_substring': False})

        harmony = job.get('harmony_audits', {}).get(candidate_id)
        if not harmony:
            link_issues.append({'candidate_id': candidate_id, 'problem': 'missing harmony audit'})
            continue
        if (harmony.get('candidate_id'), harmony.get('candidate_revision'), harmony.get('content_hash')) != (
            candidate_id, candidate.get('revision'), candidate.get('content_hash')
        ):
            link_issues.append({'candidate_id': candidate_id, 'problem': 'VP08 ID/revision/hash mismatch'})
        for role in ('fashion', 'culture', 'art'):
            if harmony.get('source_scores', {}).get(role) != reported_scores.get(role):
                link_issues.append({'candidate_id': candidate_id, 'problem': f'VP08 source_scores.{role} mismatch',
                                    'VP08': harmony.get('source_scores', {}).get(role),
                                    'specialist': reported_scores.get(role)})

        harmony_calculated, unknown, invalid = weighted_score(
            harmony.get('harmony_ratings'), config['rubrics']['harmony'])
        if harmony_calculated != harmony.get('harmony_score'):
            harmony_mismatches.append({'candidate_id': candidate_id,
                                       'reported': harmony.get('harmony_score'),
                                       'rubric_calculated': harmony_calculated})
        if unknown:
            link_issues.append({'candidate_id': candidate_id, 'problem': 'harmony has unknown applicable rubric IDs',
                                'criterion_ids': unknown})
        for conflict in harmony.get('cross_domain_conflicts', []):
            if isinstance(conflict, dict):
                for evidence in conflict.get('evidence', []):
                    quote = evidence.get('quote')
                    if quote and quote not in candidate.get('image_prompt', ''):
                        quote_issues.append({'candidate_id': candidate_id, 'role': 'harmony',
                                             'check_id': conflict.get('conflict_id'), 'quote': quote,
                                             'quote_is_prompt_substring': False})
        nonfinite.extend({'candidate_id': candidate_id, 'role': 'harmony', **item} for item in invalid)

        def total(values):
            active = {role: weight for role, weight in weights.items() if values.get(role) is not None}
            if any(not finite(values.get(role)) for role in active):
                return None
            den = sum(active.values())
            return round(sum(active[role] * values[role] for role in active) / den, 2) if den else None

        values_from_vp08 = {**harmony.get('source_scores', {}), 'harmony': harmony.get('harmony_score')}
        calculated_from_vp08 = total(values_from_vp08)
        if calculated_from_vp08 != harmony.get('proposed_total'):
            total_mismatches.append({'candidate_id': candidate_id,
                                     'vp08_proposed_total': harmony.get('proposed_total'),
                                     'balanced_recalculated_from_vp08_inputs': calculated_from_vp08})
        calculated_from_rubric = total({**calculated_scores, 'harmony': harmony_calculated})

        for field, value in [('harmony_score', harmony.get('harmony_score')),
                             ('proposed_total', harmony.get('proposed_total')),
                             *[(f'source_scores.{role}', value) for role, value in harmony.get('source_scores', {}).items()]]:
            if value is not None and not finite(value):
                nonfinite.append({'candidate_id': candidate_id, 'field': field, 'value': repr(value)})
        rows.append({'candidate_id': candidate_id, 'title': candidate.get('title'),
                     'revision': candidate.get('revision'), 'content_hash': candidate.get('content_hash'),
                     'specialist_reported': reported_scores, 'specialist_rubric_calculated': calculated_scores,
                     'specialist_matches': specialist_match, 'harmony_reported': harmony.get('harmony_score'),
                     'harmony_rubric_calculated': harmony_calculated,
                     'harmony_matches': harmony_calculated == harmony.get('harmony_score'),
                     'vp08_source_scores': harmony.get('source_scores'),
                     'vp08_proposed_total': harmony.get('proposed_total'),
                     'balanced_recalculated_from_vp08_inputs': calculated_from_vp08,
                     'balanced_recalculated_from_rubric_scores': calculated_from_rubric,
                     'vp08_total_matches_its_inputs': calculated_from_vp08 == harmony.get('proposed_total')})

    for entry in job.get('ranking', {}).get('ranked', []):
        ranked_candidate = entry.get('candidate', {})
        candidate_id = ranked_candidate.get('candidate_id')
        base = candidates.get(candidate_id)
        card = next((c for c in job.get('cards', []) if c.get('candidate_id') == candidate_id), None)
        if not base or any(ranked_candidate.get(k) != base.get(k) for k in ('revision', 'content_hash')):
            link_issues.append({'candidate_id': candidate_id, 'problem': 'ranked candidate ID/revision/hash differs from prompt pool'})
        if not card or not base or any(card.get(k) != base.get(k) for k in ('revision', 'content_hash', 'image_prompt')):
            link_issues.append({'candidate_id': candidate_id, 'problem': 'card differs from prompt pool'})
        if entry.get('score') != job.get('harmony_audits', {}).get(candidate_id, {}).get('proposed_total'):
            link_issues.append({'candidate_id': candidate_id, 'problem': 'ranking score differs from VP08 total'})
    for prompt in job.get('image_prompts', []):
        candidate = candidates.get(prompt.get('candidate_id'))
        if not candidate or prompt.get('prompt') != candidate.get('image_prompt') or prompt.get('content_hash') != candidate.get('content_hash'):
            link_issues.append({'candidate_id': prompt.get('candidate_id'), 'problem': 'image_prompts entry differs from candidate'})

    ranked_all = [entry.get('candidate', {}).get('candidate_id') for entry in job.get('ranking', {}).get('ranked', [])]
    top_api = ranked_all[:3]
    card_ids = [card.get('candidate_id') for card in job.get('cards', [])]
    rank_membership = [{'candidate_id': cid, 'rank': index + 1, 'in_cards': cid in card_ids,
                        'in_top_three': index < 3} for index, cid in enumerate(ranked_all)]
    top_three_membership = {'top_three_candidate_ids': top_api, 'card_candidate_ids': card_ids,
                            'all_top_three_present_in_cards': all(cid in card_ids for cid in top_api),
                            'all_cards_are_top_three': all(cid in top_api for cid in card_ids),
                            'exact_set_match': set(top_api) == set(card_ids)}
    ordered = sorted(rows, key=lambda row: (-(row['balanced_recalculated_from_vp08_inputs'] or 0), row['candidate_id']))
    result = {
        'snapshot': str(args.snapshot), 'request_id': job.get('request_id'), 'revision': job.get('revision'),
        'status': job.get('status'), 'provider': job.get('provider'), 'render_image': job.get('render_image'),
        'model': job.get('manifest', {}).get('text_model'), 'candidate_count': len(candidates),
        'cards_count': len(job.get('cards', [])), 'scoring_profile': profile,
        'rubric_version': job.get('manifest', {}).get('rubric_version'), 'weights': weights,
        'formulas': {'specialist_and_harmony': 'round(100 * sum(weight * rating/5 for applicable criteria) / sum(applicable weights), 2)',
                     'balanced_total': 'round(sum(active role weights * score) / sum(active role weights), 2)'},
        'candidates': rows, 'rank_membership': rank_membership,
        'top_three_membership': top_three_membership, 'top_three_api_order': top_api,
        'top_three_recalculated_from_vp08_inputs': [row['candidate_id'] for row in ordered[:3]],
        'quote_substring_issues': quote_issues, 'specialist_rubric_mismatches': specialist_mismatches,
        'harmony_rubric_mismatches': harmony_mismatches, 'vp08_balanced_total_mismatches': total_mismatches,
        'link_integrity_issues': link_issues, 'non_finite_scores': nonfinite,
        'summary': {'all_observed_quotes_are_candidate_prompt_substrings': not quote_issues,
                    'all_specialist_scores_match_rubric': not specialist_mismatches,
                    'all_harmony_scores_match_rubric': not harmony_mismatches,
                    'all_vp08_totals_match_their_own_inputs': not total_mismatches,
                    'all_top_three_candidates_present_as_cards': top_three_membership['all_top_three_present_in_cards'],
                    'cards_exactly_match_top_three_set': top_three_membership['exact_set_match'],
                    'all_links_valid': not link_issues, 'all_scores_finite': not nonfinite}
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'request_id': result['request_id'], 'status': result['status'],
                      'candidates': result['candidate_count'], 'cards': result['cards_count'],
                      'quote_issues': len(quote_issues), 'specialist_score_mismatches': len(specialist_mismatches),
                      'harmony_score_mismatches': len(harmony_mismatches),
                      'VP08_total_mismatches': len(total_mismatches), 'link_issues': len(link_issues),
                      'non_finite_scores': len(nonfinite), 'top3': top_api,
                      'top_three_membership': top_three_membership}, ensure_ascii=False))


if __name__ == '__main__':
    main()
