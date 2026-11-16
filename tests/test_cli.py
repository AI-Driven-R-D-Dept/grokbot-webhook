#!/usr/bin/env python3
"""grokbot_webhook.py のテスト。手元に立てた偽の Webhook サーバーを相手にするので、
本物の Grok Bot は動かず、キーも要らない。

    python3 -m unittest discover -s tests -v
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

SCRIPT = (Path(__file__).resolve().parent.parent
          / "plugins/grokbot-webhook/skills/setup/scripts/grokbot_webhook.py")
GOOD_KEY = "crsr_test_key_for_unit_tests"


class FakeWebhook(BaseHTTPRequestHandler):
    """本物と同じ応答の形を返す偽サーバー。届いた依頼を server.received に貯める。"""

    def log_message(self, *args):
        pass

    def _reply(self, status, obj):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        auth = self.headers.get("Authorization", "")
        if not auth:
            return self._reply(401, {"code": "error", "message": "Missing Authorization header. Use Authorization: Bearer <key>."})
        if auth != f"Bearer {GOOD_KEY}":
            return self._reply(401, {"code": "error", "message": "Invalid API key"})
        payload = json.loads(raw)
        self.server.received.append(payload)
        # 依頼文の最後に「返信ファイル: <名前>」があれば、bot の代わりに返事を書く
        reply_dir = self.server.reply_dir
        for line in payload.get("context", "").splitlines():
            if line.startswith("返信ファイル:") and reply_dir and self.server.write_reply:
                name = line.split(":", 1)[1].strip()
                threading.Timer(0.5, lambda: (reply_dir / name).write_text("偽 bot の返事\n", encoding="utf-8")).start()
        self._reply(200, {"success": True, "runUuid": "00000000-0000-0000-0000-000000000001"})


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.reply_dir = root / "replies"
        self.config = root / "config" / "env"
        self.server = HTTPServer(("127.0.0.1", 0), FakeWebhook)
        self.server.received = []
        self.server.reply_dir = self.reply_dir
        self.server.write_reply = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}/automations/webhook/test-routine"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def run_cli(self, *args, stdin=None, env=None):
        e = {k: v for k, v in os.environ.items() if not k.startswith("GROKBOT_")}
        e.update({
            "GROKBOT_WEBHOOK_CONFIG": str(self.config),
            "GROKBOT_REPLY_DIR": str(self.reply_dir),
            "CLAUDE_CONFIG_DIR": str(Path(self.tmp.name) / "claude"),   # skill の作成先を本物の ~/.claude から外す
            "GROKBOT_WEBHOOK_ALLOW_ANY_HOST": "1",   # テスト用: 偽サーバーは手元の http
        })
        e.update(env or {})
        return subprocess.run([sys.executable, str(SCRIPT), *args], input=stdin,
                              capture_output=True, text=True, env=e, timeout=60)

    def configured(self, key=GOOD_KEY):
        return {"GROKBOT_WEBHOOK_URL": self.url, "GROKBOT_WEBHOOK_KEY": key}

    # ---- check
    def test_check_without_config_exits_2(self):
        r = self.run_cli("check")
        self.assertEqual(r.returncode, 2)
        self.assertIn("[NG]", r.stdout)

    def test_check_never_calls_the_webhook(self):
        r = self.run_cli("check", env=self.configured())
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.server.received, [])

    def test_check_does_not_print_the_key(self):
        r = self.run_cli("check", env=self.configured())
        self.assertNotIn(GOOD_KEY, r.stdout + r.stderr)

    # ---- save
    def test_save_from_stdin_writes_private_file(self):
        r = self.run_cli("save", "--no-skill", "--url", self.url, stdin=GOOD_KEY + "\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn(GOOD_KEY, r.stdout + r.stderr)
        text = self.config.read_text(encoding="utf-8")
        self.assertIn(f"GROKBOT_WEBHOOK_KEY={GOOD_KEY}", text)
        if os.name == "posix":
            self.assertEqual(self.config.stat().st_mode & 0o077, 0)

    def test_save_accepts_the_header_form(self):
        r = self.run_cli("save", "--no-skill", "--url", self.url, stdin=f"Authorization: Bearer {GOOD_KEY}\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f"GROKBOT_WEBHOOK_KEY={GOOD_KEY}\n", self.config.read_text(encoding="utf-8"))

    def test_save_rejects_empty_key_and_bad_url(self):
        self.assertEqual(self.run_cli("save", "--no-skill", "--url", self.url, stdin="\n").returncode, 2)
        self.assertEqual(self.run_cli("save", "--no-skill", "--url", "https://example.com/other", stdin=GOOD_KEY).returncode, 2)

    def test_save_without_url_and_without_terminal_exits_2(self):
        r = self.run_cli("save", stdin="")
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("Traceback", r.stderr)

    def test_saved_config_is_used_by_send(self):
        self.run_cli("save", "--no-skill", "--url", self.url, stdin=GOOD_KEY + "\n")
        r = self.run_cli("send", "こんにちは")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.server.received[0], {"context": "こんにちは"})

    # ---- send
    def test_send_posts_context_once(self):
        r = self.run_cli("send", "日本語の依頼", env=self.configured())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["sent"], True)
        self.assertEqual(self.server.received, [{"context": "日本語の依頼"}])

    def test_send_reads_stdin(self):
        r = self.run_cli("send", "-", stdin="標準入力から\n2 行目\n", env=self.configured())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.server.received[0]["context"], "標準入力から\n2 行目")

    def test_send_wait_prints_reply_and_adds_reply_line(self):
        r = self.run_cli("send", "--wait", "--timeout", "20", "答えて", env=self.configured())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "偽 bot の返事")
        ctx = self.server.received[0]["context"]
        self.assertTrue(ctx.startswith("答えて\n\n返信ファイル: r-"))
        self.assertRegex(ctx.splitlines()[-1], r"^返信ファイル: r-\d+-[0-9a-f]{8}\.md$")
        self.assertEqual(len(self.server.received), 1)

    def test_send_wait_times_out_with_4_and_does_not_resend(self):
        self.server.write_reply = False
        r = self.run_cli("send", "--wait", "--timeout", "3", "答えて", env=self.configured())
        self.assertEqual(r.returncode, 4)
        self.assertEqual(len(self.server.received), 1)

    def test_wrong_key_exits_3_without_leaking_it(self):
        r = self.run_cli("send", "x", env=self.configured(key="crsr_wrong_key_value"))
        self.assertEqual(r.returncode, 3)
        self.assertIn("401", r.stderr)
        self.assertNotIn("crsr_wrong_key_value", r.stdout + r.stderr)

    def test_unreachable_exits_3(self):
        env = {"GROKBOT_WEBHOOK_URL": "http://127.0.0.1:9/automations/webhook/x", "GROKBOT_WEBHOOK_KEY": GOOD_KEY}
        r = self.run_cli("send", "x", env=env)
        self.assertEqual(r.returncode, 3)
        self.assertNotIn("Traceback", r.stderr)

    def test_empty_request_exits_2(self):
        r = self.run_cli("send", "-", stdin="   \n", env=self.configured())
        self.assertEqual(r.returncode, 2)
        self.assertEqual(self.server.received, [])

    def test_key_is_never_sent_to_other_hosts(self):
        strict = {"GROKBOT_WEBHOOK_ALLOW_ANY_HOST": ""}
        r = self.run_cli("send", "x", env={**self.configured(), **strict})
        self.assertEqual(r.returncode, 2)
        self.assertEqual(self.server.received, [])
        for bad in ("https://evil.example/automations/webhook/x",
                    "https://cursor.sh.evil.example/automations/webhook/x",
                    "http://api2.cursor.sh/automations/webhook/x"):
            env = {"GROKBOT_WEBHOOK_URL": bad, "GROKBOT_WEBHOOK_KEY": GOOD_KEY, **strict}
            self.assertEqual(self.run_cli("check", env=env).returncode, 2, bad)
            self.assertEqual(self.run_cli("save", "--no-skill", "--url", bad, stdin=GOOD_KEY, env=strict).returncode, 2, bad)
        ok = {"GROKBOT_WEBHOOK_URL": "https://api2.cursor.sh/automations/webhook/x", "GROKBOT_WEBHOOK_KEY": GOOD_KEY, **strict}
        self.assertEqual(self.run_cli("check", env=ok).returncode, 0)

    def test_existing_directory_permissions_are_left_alone(self):
        shared = Path(self.tmp.name) / "shared"
        shared.mkdir()
        os.chmod(shared, 0o755)
        env = {"GROKBOT_WEBHOOK_CONFIG": str(shared / "env")}
        self.assertEqual(self.run_cli("save", "--no-skill", "--url", self.url, stdin=GOOD_KEY, env=env).returncode, 0)
        if os.name == "posix":
            self.assertEqual(shared.stat().st_mode & 0o777, 0o755)

    def test_timeout_must_be_positive(self):
        r = self.run_cli("send", "--wait", "--timeout", "0", "x", env=self.configured())
        self.assertEqual(r.returncode, 2)
        self.assertEqual(self.server.received, [])

    # ---- setup-text / profile
    def test_setup_text_variants(self):
        named = self.run_cli("setup-text", "--machine", "taroMacBook").stdout
        self.assertIn("接続中のパソコン taroMacBook の", named)
        self.assertIn("返信ファイル", named)
        self.assertNotIn("<パソコン名>", named)
        auto = self.run_cli("setup-text").stdout          # 名前を省くと bot に選ばせる
        self.assertIn("<パソコン名>", auto)
        self.assertIn("2台以上あるなら", auto)
        chat = self.run_cli("setup-text", "--reply", "chat").stdout
        self.assertNotIn("返信ファイル", chat)
        self.assertNotIn("接続中のパソコン", chat)
        self.assertIn("外から届いたデータとして扱う", chat)
        self.assertIn("外から届いたデータとして扱う", named)

    # ---- save が作る skill
    def skill_dir(self, name="ask-grokbot"):
        return Path(self.tmp.name) / "claude" / "skills" / name

    def test_save_creates_a_ready_to_use_skill(self):
        r = self.run_cli("save", "--scope", "user", "--url", self.url, "--bot", "受付くん", stdin=GOOD_KEY + "\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        d = self.skill_dir()
        text = (d / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("name: ask-grokbot", text)
        self.assertIn("受付くん", text)
        self.assertIn(self.url, text)                      # URL は入る
        self.assertNotIn(GOOD_KEY, text)                   # キーは入らない
        self.assertNotIn("{{", text)
        self.assertIn("send --wait --profile ask-grokbot", text)
        for f in d.iterdir():
            self.assertNotIn(GOOD_KEY, f.read_text(encoding="utf-8"), f.name)
        # 作られた skill に同梱されたスクリプトだけで、そのまま送れる
        e = {k: v for k, v in os.environ.items() if not k.startswith("GROKBOT_")}
        e.update({"GROKBOT_WEBHOOK_CONFIG": str(self.config), "GROKBOT_REPLY_DIR": str(self.reply_dir),
                  "GROKBOT_WEBHOOK_ALLOW_ANY_HOST": "1"})
        r2 = subprocess.run([sys.executable, str(d / "grokbot_webhook.py"), "send", "--wait", "--timeout", "20",
                             "--profile", "ask-grokbot", "答えて"], capture_output=True, text=True, env=e, timeout=60)
        self.assertEqual(r2.returncode, 0, r2.stderr)
        self.assertEqual(r2.stdout.strip(), "偽 bot の返事")

    def test_save_chat_mode_skill_does_not_wait(self):
        self.run_cli("save", "--scope", "user", "--url", self.url, "--reply", "chat", stdin=GOOD_KEY + "\n")
        text = (self.skill_dir() / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("send --profile ask-grokbot", text)
        self.assertNotIn("send --wait", text)
        self.assertNotIn("--timeout", text)          # 待たない形には、待つ前提の文を残さない
        self.assertNotIn("| 4 |", text)
        self.assertNotIn("{{", text)

    def test_save_project_scope_and_custom_name(self):
        work = Path(self.tmp.name) / "work"
        work.mkdir()
        e = {k: v for k, v in os.environ.items() if not k.startswith("GROKBOT_")}
        e.update({"GROKBOT_WEBHOOK_CONFIG": str(self.config), "GROKBOT_WEBHOOK_ALLOW_ANY_HOST": "1"})
        r = subprocess.run([sys.executable, str(SCRIPT), "save", "--url", self.url, "--scope", "project",
                            "--skill-name", "ask-sales-bot"], input=GOOD_KEY + "\n", capture_output=True,
                           text=True, env=e, cwd=work, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((work / ".claude" / "skills" / "ask-sales-bot" / "SKILL.md").is_file())
        self.assertIn("GROKBOT_WEBHOOK_KEY_ASK_SALES_BOT=", self.config.read_text(encoding="utf-8"))

    def test_save_does_not_overwrite_someone_elses_skill(self):
        d = self.skill_dir()
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text("自分で書いた skill\n", encoding="utf-8")
        r = self.run_cli("save", "--scope", "user", "--url", self.url, stdin=GOOD_KEY + "\n")
        self.assertEqual(r.returncode, 2)
        self.assertEqual((d / "SKILL.md").read_text(encoding="utf-8"), "自分で書いた skill\n")

    # ---- クリップボード経由 (偽のクリップボードコマンドを PATH の先頭に置いて試す)
    def fake_clipboard(self):
        """pbpaste / pbcopy の代わり。clip.txt の中身を返し、書き込みを受ける。"""
        bin_dir = Path(self.tmp.name) / "bin"
        bin_dir.mkdir()
        clip = Path(self.tmp.name) / "clip.txt"
        clip.write_text("前から入っていた文字", encoding="utf-8")
        (bin_dir / "pbpaste").write_text(f'#!/bin/sh\ncat "{clip}"\n')
        (bin_dir / "pbcopy").write_text(f'#!/bin/sh\ncat > "{clip}"\n')
        for f in bin_dir.iterdir():
            f.chmod(0o755)
        return clip, {"PATH": f"{bin_dir}:{os.environ['PATH']}"}

    def test_setup_text_copy_puts_text_on_clipboard(self):
        clip, env = self.fake_clipboard()
        r = self.run_cli("setup-text", "--copy", "--machine", "taroMacBook", env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("Webhookが発火したとき", r.stdout)      # 画面には文章を出さない
        self.assertIn("接続中のパソコン taroMacBook の", clip.read_text(encoding="utf-8"))

    def test_save_from_clipboard_waits_for_url_and_key(self):
        clip, env = self.fake_clipboard()

        def person():            # 人がアプリでコピーのボタンを順に押す
            time.sleep(1.5)
            clip.write_text(self.url, encoding="utf-8")
            time.sleep(1.5)
            clip.write_text(f"Authorization: Bearer {GOOD_KEY}", encoding="utf-8")
        threading.Thread(target=person, daemon=True).start()
        r = self.run_cli("save", "--scope", "user", "--from-clipboard", "--clip-timeout", "20", "--bot", "受付くん", env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn(GOOD_KEY, r.stdout + r.stderr)
        self.assertNotIn("/automations/webhook/test-routine", r.stdout + r.stderr.replace(str(self.config), ""))
        conf = self.config.read_text(encoding="utf-8")
        self.assertIn(f"GROKBOT_WEBHOOK_KEY_ASK_GROKBOT={GOOD_KEY}\n", conf)
        self.assertIn(f"GROKBOT_WEBHOOK_URL_ASK_GROKBOT={self.url}\n", conf)
        self.assertNotIn(GOOD_KEY, clip.read_text(encoding="utf-8"))   # クリップボードは上書きされる
        self.assertTrue((self.skill_dir() / "SKILL.md").is_file())

    def test_save_from_clipboard_ignores_what_was_there_before_and_times_out(self):
        clip, env = self.fake_clipboard()
        clip.write_text(GOOD_KEY, encoding="utf-8")                    # 前から入っていたキーは使わない
        r = self.run_cli("save", "--scope", "user", "--from-clipboard", "--clip-timeout", "3", "--url", self.url, env=env)
        self.assertEqual(r.returncode, 4)
        self.assertFalse(self.config.exists())

    def test_save_rejects_command_text_pasted_as_key(self):
        r = self.run_cli("save", "--no-skill", "--url", self.url, stdin="! pbpaste | python3 x save --url y\n")
        self.assertEqual(r.returncode, 2)
        self.assertFalse(self.config.exists())

    # ---- 公開前レビューで見つかった穴の再発防止
    def test_save_requires_scope_when_creating_a_skill(self):
        r = self.run_cli("save", "--url", self.url, stdin=GOOD_KEY + "\n")
        self.assertEqual(r.returncode, 2)
        self.assertIn("--scope", r.stderr)
        self.assertFalse(self.config.exists())
        self.assertFalse(self.skill_dir().exists())

    def test_save_rejects_strings_that_are_not_keys(self):
        for bad in ("abc", "crsr_X", "crsr_has space_in_it_1234567890"):
            r = self.run_cli("save", "--no-skill", "--url", self.url, stdin=bad + "\n")
            self.assertEqual(r.returncode, 2, bad)
        self.assertFalse(self.config.exists())

    def test_url_with_newline_or_extra_parts_is_rejected(self):
        for bad in (self.url + "\nGROKBOT_WEBHOOK_URL_OTHER=http://attacker.example/automations/webhook/x",
                    self.url + "?next=http://attacker.example", self.url + " extra",
                    self.url.replace("http://", "http://user@")):
            env = {"GROKBOT_WEBHOOK_URL": bad, "GROKBOT_WEBHOOK_KEY": GOOD_KEY}
            self.assertEqual(self.run_cli("check", env=env).returncode, 2, repr(bad))
            self.assertEqual(self.run_cli("send", "x", env=env).returncode, 2, repr(bad))
            self.assertEqual(self.run_cli("save", "--no-skill", "--url", bad, stdin=GOOD_KEY).returncode, 2, repr(bad))
        self.assertEqual(self.server.received, [])
        self.assertFalse(self.config.exists())

    def test_redirect_is_not_followed_so_the_key_stays_put(self):
        seen = []

        class Catcher(BaseHTTPRequestHandler):       # リダイレクト先のふりをするサーバー
            def log_message(self, *a):
                pass

            def do_POST(self):
                seen.append(self.headers.get("Authorization"))
                self.send_response(200)
                self.end_headers()
            do_GET = do_POST

        other = HTTPServer(("127.0.0.1", 0), Catcher)
        threading.Thread(target=other.serve_forever, daemon=True).start()

        class Redirector(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{other.server_port}/automations/webhook/stolen")
                self.end_headers()

        first = HTTPServer(("127.0.0.1", 0), Redirector)
        threading.Thread(target=first.serve_forever, daemon=True).start()
        try:
            env = {"GROKBOT_WEBHOOK_URL": f"http://127.0.0.1:{first.server_port}/automations/webhook/x",
                   "GROKBOT_WEBHOOK_KEY": GOOD_KEY}
            r = self.run_cli("send", "x", env=env)
            self.assertEqual(r.returncode, 3)
            self.assertEqual(seen, [])
            self.assertNotIn("Traceback", r.stderr)
        finally:
            for srv in (first, other):
                srv.shutdown()
                srv.server_close()

    def test_reply_file_is_removed_after_reading_unless_kept(self):
        r = self.run_cli("send", "--wait", "--timeout", "20", "答えて", env=self.configured())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(list(self.reply_dir.glob("*.md")), [])
        r = self.run_cli("send", "--wait", "--keep-reply", "--timeout", "20", "答えて", env=self.configured())
        self.assertEqual(len(list(self.reply_dir.glob("*.md"))), 1)

    def test_save_rejects_url_pasted_as_key_and_bad_names(self):
        self.assertEqual(self.run_cli("save", "--no-skill", "--url", self.url, stdin=self.url + "\n").returncode, 2)
        self.assertEqual(self.run_cli("save", "--scope", "user", "--url", self.url, "--skill-name", "Bad Name", stdin=GOOD_KEY).returncode, 2)

    def test_save_refuses_profile_together_with_a_skill(self):
        r = self.run_cli("save", "--url", self.url, "--scope", "user", "--profile", "work", stdin=GOOD_KEY + "\n")
        self.assertEqual(r.returncode, 2)
        self.assertIn("--no-skill", r.stderr)
        self.assertFalse(self.skill_dir().exists())

    def test_bot_name_with_yaml_characters_keeps_the_skill_readable(self):
        r = self.run_cli("save", "--url", self.url, "--scope", "user", "--bot", 'Bot: #1 "x"', stdin=GOOD_KEY + "\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        line = [l for l in (self.skill_dir() / "SKILL.md").read_text(encoding="utf-8").splitlines()
                if l.startswith("description: ")][0]
        value = json.loads(line[len("description: "):])     # 二重引用符の文字列として読める
        self.assertIn('Bot: #1 "x" に頼んで', value)

    def test_profile_uses_suffixed_names(self):
        env = {"GROKBOT_WEBHOOK_URL_WORK": self.url, "GROKBOT_WEBHOOK_KEY_WORK": GOOD_KEY}
        self.assertEqual(self.run_cli("send", "--profile", "work", "x", env=env).returncode, 0)
        self.assertEqual(self.run_cli("send", "x", env=env).returncode, 2)


if __name__ == "__main__":
    unittest.main()
