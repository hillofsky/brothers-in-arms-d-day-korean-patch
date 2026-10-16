import argparse, json
p=argparse.ArgumentParser()
p.add_argument("--detail", required=True)
a=p.parse_args()
print(json.dumps({"detail":a.detail}, ensure_ascii=False))
