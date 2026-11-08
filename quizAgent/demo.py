"""Run from repository root: python3 -m quizAgent.demo [--interactive]."""

import argparse
import json

from quizAgent import QuizAgent
from .errors import QuizError
from llm.contracts import ModelError
from llm import MockLLM, OllamaClient
from quizAgent.mock_backend import MockBackend


def main():
    parser = argparse.ArgumentParser(description="Local Quiz Agent prototype")
    parser.add_argument("--interactive", action="store_true", help="Answer questions in the terminal")
    parser.add_argument("--course", default="NetworkSecurity", help="Indexed course folder name")
    parser.add_argument("--topic", help="Topic to search in the course materials")
    parser.add_argument("--config", help="Ollama JSON settings file (OLLAMA_CONFIG; default: llm/ollama.json)")
    inspection = parser.add_mutually_exclusive_group()
    inspection.add_argument("--show-config", action="store_true", help="Print resolved Ollama settings without connecting")
    parser.add_argument("--model", help="Ollama model (OLLAMA_MODEL; default: qwen3.5:9b)")
    parser.add_argument("--ollama-url", help="Host URL including port (OLLAMA_BASE_URL; default: http://127.0.0.1:11434)")
    parser.add_argument("--timeout", type=float, help="Ollama timeout in seconds (OLLAMA_TIMEOUT; default: 120)")
    inspection.add_argument("--check-connection", action="store_true", help="Check host connectivity and model installation, then exit")
    parser.add_argument("--mock", action="store_true", help="Explicit offline test mode; no Ollama calls")
    args = parser.parse_args()
    if args.mock and (args.check_connection or args.show_config or args.config is not None or args.model is not None
                      or args.ollama_url is not None or args.timeout is not None):
        parser.error("--mock cannot be combined with Ollama options.")
    try:
        model = MockLLM() if args.mock else OllamaClient(
            args.model, base_url=args.ollama_url, timeout=args.timeout, config_path=args.config,
        )
        if args.show_config:
            print(json.dumps(model.settings.to_dict(), indent=2))
            return
        if args.check_connection:
            print(json.dumps(model.check_connection(), indent=2))
            return
        backend = MockBackend(QuizAgent(model), {"alice": (args.course,)})
        public = backend.create_quiz("alice", {
            "course_id": args.course, "mode": "topic" if args.topic else "random",
            "topic_id": args.topic,
            "question_counts": {"multiple_choice": 3, "true_false": 2, "open_ended": 1},
        })
        print("PUBLIC QUIZ (indexed course material)")
        print(json.dumps(public, indent=2))
        answers = {}
        for q in public["questions"]:
            if args.interactive:
                print("\n" + q["text"])
                for label, option in q["options"].items():
                    print(f"  {label}: {option}")
                answer = input("Answer: ").strip()
                if q["type"] == "true_false":
                    while answer.lower() not in ("true", "false"):
                        answer = input("Enter true or false: ").strip()
                    answer = answer.lower() == "true"
                elif q["type"] == "multiple_choice":
                    answer = answer.upper()
                    while answer not in q["options"]:
                        answer = input("Enter A, B, C, or D: ").strip().upper()
                else:
                    while not answer or len(answer) > 4000:
                        answer = input("Enter 1–4000 characters: ").strip()
            else:
                answer = {"multiple_choice": "A", "true_false": True,
                          "open_ended": "A firewall filters traffic according to a security policy."}[q["type"]]
            answers[q["question_id"]] = answer
        print("\nSUBMITTED ANSWERS")
        print(json.dumps(answers, indent=2))
        result = backend.submit_answers("alice", public["attempt_id"], answers)
        print("\nCOMMITTED RESULT")
        print(json.dumps(result, indent=2))
    except (QuizError, ModelError) as exc:
        parser.exit(1, f"Prototype error: {exc}\n")
    except ValueError as exc:
        parser.error(str(exc))
    except (EOFError, KeyboardInterrupt):
        parser.exit(1, "\nDemo cancelled.\n")


if __name__ == "__main__":
    main()
