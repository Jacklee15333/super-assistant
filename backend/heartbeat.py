"""
heartbeat.py — 心跳后台进程

每隔一段时间"叫醒"agent：让它读 heartbeat.md，看有没有事做。
- 有事 -> 做，并把结果写进当天笔记。
- 没事 -> 模型回 SLEEP，本进程安静地继续等下一次。

单独运行：  python heartbeat.py
（界面里也有按钮可以手动触发一次心跳，方便你立刻看到效果。）
"""

import time
import datetime
import argparse

from agent_core import (
    make_client, build_system_prompt, read_memory_file,
    run_agent_autodeny, append_note,
)

# 心跳给 agent 的提示语
HEARTBEAT_PROMPT = (
    "【心跳】你被定时叫醒了。请阅读下面的待办清单，判断现在有没有该做的事。\n"
    "如果有，就用工具去做，并简短说明做了什么。\n"
    "如果没有任何该做的事，只回复一个词：SLEEP。\n\n"
    "=== heartbeat.md ===\n{heartbeat}\n"
)


def run_one_beat(use_local=True, model="qwen2.5", verbose=True):
    """触发一次心跳，返回 agent 的回复。供界面和循环复用。"""
    client = make_client(use_local)
    heartbeat = read_memory_file("heartbeat.md")
    reminders = read_memory_file("reminders.md")
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M（%A）")
    extra = (f"\n=== 当前时间 ===\n{now}\n"
             f"=== 定时提醒 reminders.md ===\n{reminders}\n"
             "如果有提醒到点了，就通知用户并说明；没到点的不要动。")
    messages = [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": HEARTBEAT_PROMPT.format(heartbeat=heartbeat) + extra},
    ]

    def on_tool(name, args, result):
        if verbose:
            print(f"  [工具] {name}({args}) -> {str(result)[:80]}")

    reply, _ = run_agent_autodeny(client, model, messages, on_tool=on_tool)

    stamp = datetime.datetime.now().strftime("%H:%M:%S")
    if reply.strip().upper().startswith("SLEEP"):
        if verbose:
            print(f"[{stamp}] 没事，继续休眠。")
    else:
        if verbose:
            print(f"[{stamp}] 干活了：{reply}")
        append_note(f"[心跳] {reply}")
        # 心跳干完活，尝试推到微信（配了 Server酱才会真的发）
        try:
            import push_serverchan
            push_serverchan.push("超能小助心跳", reply)
        except Exception:
            pass
    return reply


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=int, default=300,
                    help="心跳间隔秒数，默认 300（5分钟）")
    ap.add_argument("--cloud", action="store_true",
                    help="用云端模型而非本地 Ollama")
    ap.add_argument("--model", default="qwen2.5",
                    help="模型名，云端可填 gpt-4o-mini 等")
    ap.add_argument("--watch-every", type=int, default=12,
                    help="每隔几次心跳查一遍竞品，默认12（约1小时@5分钟间隔）")
    ap.add_argument("--daily-student", default="",
                    help="给哪个学生每天定时推英语任务，留空则不推")
    ap.add_argument("--daily-hour", type=int, default=18,
                    help="每天几点推英语任务，默认18点")
    args = ap.parse_args()

    print(f"心跳启动，每 {args.interval} 秒一次。"
          f"每 {args.watch_every} 次心跳查一遍竞品。Ctrl+C 退出。")
    if args.daily_student:
        print(f"每天 {args.daily_hour} 点给「{args.daily_student}」推英语任务。")
    beat_count = 0
    last_task_date = None
    while True:
        try:
            run_one_beat(use_local=not args.cloud, model=args.model)
            beat_count += 1
            # 定时检查竞品
            if args.watch_every > 0 and beat_count % args.watch_every == 0:
                try:
                    import competitor_watch
                    alerts, _ = competitor_watch.run_check(
                        use_local=not args.cloud, model=args.model)
                    if alerts:
                        stamp = datetime.datetime.now().strftime("%H:%M")
                        print(f"[{stamp}] 竞品有动静（已推送）：{len(alerts)} 条")
                except Exception as e:
                    print(f"竞品检查出错（忽略）：{e}")
            # 每日英语任务
            if args.daily_student:
                now = datetime.datetime.now()
                today = now.date().isoformat()
                if now.hour >= args.daily_hour and last_task_date != today:
                    try:
                        import tutor
                        tutor.generate_daily_task(
                            student=args.daily_student,
                            use_local=not args.cloud, model=args.model)
                        last_task_date = today
                        print(f"[{now.strftime('%H:%M')}] 已推送今日英语任务"
                              f"给「{args.daily_student}」")
                    except Exception as e:
                        print(f"推送英语任务出错（忽略）：{e}")
        except Exception as e:
            print(f"心跳出错（忽略，继续）：{e}")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
