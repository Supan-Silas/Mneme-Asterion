"""Recompute LoCoMo-Refined means and sample standard deviations."""
import json
from pathlib import Path
from statistics import mean, stdev

ROOT = Path(__file__).resolve().parents[1]


def main():
    data = json.loads((ROOT / 'results/locomo_refined.json').read_text(encoding='utf-8'))
    denominator = data['questions_per_round']
    summary = {}
    for method, row in data['methods'].items():
        scores = [100 * count / denominator for count in row['correct']]
        summary[method] = {'mean_percent': mean(scores), 'sample_std_percent': stdev(scores)}
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
