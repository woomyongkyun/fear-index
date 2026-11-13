"""사용법:
  python run.py backfill   과거 데이터를 처음부터 다시 받는다 (최초 1회, 수 분 소요)
  python run.py update     최신 데이터를 받아 지수를 다시 계산한다
  python run.py build      data/ 로 사이트를 만든다 (dist/)
  python run.py all        update + build
"""
import sys

from fearindex import pipeline


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd == "backfill":
        pipeline.collect(backfill=True)
    if cmd in ("update", "all"):
        pipeline.collect()
    if cmd in ("build", "all", "backfill"):
        from fearindex import build
        build.build()


if __name__ == "__main__":
    main()
