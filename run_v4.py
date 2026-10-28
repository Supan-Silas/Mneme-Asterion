"""Final V4 entry: validate method and source before loading the original service."""
import argparse
from tools.preflight import check_file


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--env-file', required=True)
    args, _ = parser.parse_known_args()
    result = check_file(args.env_file)
    if not result['passed']:
        raise SystemExit('; '.join(result['errors']))
    from launch import main as original_main
    original_main()


if __name__ == '__main__':
    main()
