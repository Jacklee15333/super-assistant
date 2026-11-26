"""
biz_archive.py — 市场雷达的「存档库」（v183 新增）

内容库（内存里最新的 6 万条）满了，或者新闻超过 45 天，以前是直接删掉；现在挪进存档库：
  memory/biz/radar_archive/news_001.db、news_002.db …（SQLite，Python 自带，不用另外装）
每个存档库最多放 100 万条，满了自动开下一个——「用完一个再加一个」。
看 7 天、1 个月、1 年、累计的新闻列表时，先列内容库里的，再接着列存档库里的。
"""
import json
import os
import re
import sqlite3
import threading
import time
from pathlib import Path

MEM = Path(__file__).resolve().parent / "memory"
DIR = MEM / "biz" / "radar_archive"
CAP = 1_000_000                      # 每个存档库最多多少条
_LOCK = threading.RLock()
_INFO = {"n": None, "files": 0, "bytes": 0, "max_ts": 0, "min_ts": 0, "at": 0.0}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS items(key TEXT PRIMARY KEY, ts INTEGER, seen INTEGER, sid TEXT, sname TEXT, grp TEXT,
  title TEXT, url TEXT, summary TEXT, src_from TEXT, dated INTEGER, cls TEXT);
CREATE INDEX IF NOT EXISTS i_ts ON items(ts);
CREATE TABLE IF NOT EXISTS tags(key TEXT, tag TEXT, ts INTEGER);
CREATE INDEX IF NOT EXISTS t_tag ON tags(tag, ts);
CREATE INDEX IF NOT EXISTS t_key ON tags(key);
"""


def _files():
    if not DIR.exists():
        return []
    return sorted(p for p in DIR.glob("news_*.db") if re.match(r"news_\d{3,}\.db$", p.name))


def _open(p):
    c = sqlite3.connect(str(p), timeout=30, check_same_thread=False)
    c.executescript(_SCHEMA)
    return c


def _count(c):
    return c.execute("SELECT COUNT(*) FROM items").fetchone()[0]


def tags_of(ind, trk, l3):
    """一条新闻的分类标签：细分行业、新兴赛道、三级细分、一级行业（l1:电子）。"""
    t = set(ind or []) | set(trk or []) | set(l3 or [])
    t |= {"l1:" + g.split("/")[0] for g in (ind or [])}
    return sorted(t)


def add(records):
    """把挪出内容库的新闻存进存档库。records：[{key, ts, seen, sid, sname, grp, title, url, summary, from, dated, ind, trk, l3}]"""
    if not records:
        return 0
    with _LOCK:
        DIR.mkdir(parents=True, exist_ok=True)
        fs = _files()
        p = fs[-1] if fs else DIR / "news_001.db"
        c = _open(p)
        n_have = _count(c)
        done = 0
        try:
            for r in records:
                if n_have >= CAP:                                      # 这个存档库满了：开下一个
                    c.commit()
                    c.close()
                    p = DIR / ("news_%03d.db" % (len(_files()) + 1))
                    c = _open(p)
                    n_have = 0
                cls = {"ind": r.get("ind") or [], "trk": r.get("trk") or [], "l3": r.get("l3") or []}
                cur = c.execute("INSERT OR IGNORE INTO items VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                                (r["key"], int(r.get("ts") or 0), int(r.get("seen") or 0), r.get("sid", ""), r.get("sname", ""),
                                 r.get("grp", ""), (r.get("title") or "")[:200], r.get("url", ""), (r.get("summary") or "")[:300],
                                 r.get("from", ""), 1 if r.get("dated") else 0, json.dumps(cls, ensure_ascii=False)))
                if cur.rowcount:
                    c.executemany("INSERT INTO tags VALUES(?,?,?)", [(r["key"], t, int(r.get("ts") or 0)) for t in tags_of(cls["ind"], cls["trk"], cls["l3"])])
                    n_have += 1
                    done += 1
                    _INFO["max_ts"] = max(_INFO["max_ts"] or 0, int(r.get("ts") or 0))
            c.commit()
        finally:
            c.close()
        if _INFO["n"] is not None:
            _INFO["n"] += done
        _INFO["at"] = 0.0                                              # 文件大小下次重新算
        return done


def info(refresh=False):
    """存档库一共几个文件、多少条、多大。"""
    with _LOCK:
        if _INFO["n"] is None or refresh or time.time() - _INFO["at"] > 300:
            fs = _files()
            n, mx, mn = 0, 0, 0
            for p in fs:
                try:
                    c = _open(p)
                    n += _count(c)
                    a, b = c.execute("SELECT MIN(ts), MAX(ts) FROM items").fetchone()
                    c.close()
                    if b:
                        mx = max(mx, b)
                        mn = a if not mn else min(mn, a or mn)
                except Exception:
                    pass
            _INFO.update(n=n, files=len(fs), bytes=sum(p.stat().st_size for p in fs), max_ts=mx, min_ts=mn, at=time.time())
        return {"n": _INFO["n"], "files": _INFO["files"], "mb": round(_INFO["bytes"] / 1e6, 1), "max_ts": _INFO["max_ts"], "min_ts": _INFO["min_ts"]}


def query(cut=0, tags=None, grps=None, q="", sid="", limit=60, offset=0):
    """在存档库里找新闻（新的在前）。tags：命中其中任何一个就算。返回 (一共多少条, [记录])。"""
    fs = _files()
    if not fs:
        return 0, []
    where, args = [], []
    if cut:
        where.append("ts >= ?")
        args.append(int(cut))
    if grps:
        where.append("grp IN (%s)" % ",".join("?" * len(grps)))
        args += list(grps)
    if sid:
        where.append("sid = ?")
        args.append(sid)
    if q:
        where.append("(title LIKE ? OR summary LIKE ?)")
        args += ["%" + q + "%", "%" + q + "%"]
    if tags:
        where.append("key IN (SELECT key FROM tags WHERE tag IN (%s)%s)" % (",".join("?" * len(tags)), " AND ts >= ?" if cut else ""))
        args += list(tags) + ([int(cut)] if cut else [])
    w = (" WHERE " + " AND ".join(where)) if where else ""
    total, rows, skip, need = 0, [], max(0, int(offset)), max(0, int(limit))
    with _LOCK:
        for p in reversed(fs):                                         # 新的存档库在前
            try:
                c = _open(p)
                n = c.execute("SELECT COUNT(*) FROM items" + w, args).fetchone()[0]
                if need and n > skip:
                    cur = c.execute("SELECT key, ts, seen, sid, sname, grp, title, url, summary, src_from, dated, cls FROM items" + w +
                                    " ORDER BY ts DESC LIMIT ? OFFSET ?", args + [need, skip])
                    got = cur.fetchall()
                    rows += got
                    need -= len(got)
                    skip = 0
                else:
                    skip = max(0, skip - n)
                total += n
                c.close()
            except Exception:
                continue
    out = []
    for k, ts, seen, sid_, sname, grp, title, url, summ, frm, dated, cls in rows:
        try:
            cl = json.loads(cls or "{}")
        except Exception:
            cl = {}
        out.append({"key": k, "ts": ts, "seen": seen, "sid": sid_, "sname": sname, "grp": grp, "title": title, "url": url,
                    "summary": summ, "from": frm, "dated": bool(dated), "ind": cl.get("ind", []), "trk": cl.get("trk", []), "l3": cl.get("l3", [])})
    return total, out
