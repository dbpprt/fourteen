from argparse import Namespace, ArgumentParser

def main(params: Namespace) -> None:
    print(params)

def parse_args() -> Namespace:
    parser = ArgumentParser()
    parser.add_argument(
        '--input', type=str, default='data/input.txt', help='input file')
    parser.add_argument(
        '--output', type=str, default='data/output.txt', help='output file')
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    main(args)
