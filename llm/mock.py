"""Deterministic fixture model. Keyword grading is ONLY a workflow simulation."""

import random
import re

from llm.contracts import ModelError


class MockLLM:
    def generate_structured(self, *, task, instructions, input_data, output_schema):
        if task == "quiz_generation":
            return self._generate(input_data)
        if task == "quiz_grading":
            return self._grade(input_data)
        raise ModelError("Mock model supports only the two quiz tasks.")

    def _generate(self, data):
        evidence = data["evidence"]
        sample_prompts = {
            "sample_firewall_1": "Explain how a firewall decides which network traffic to allow.",
            "sample_firewall_2": "Explain what distinguishes a stateful firewall's packet decisions.",
            "sample_firewall_3": "Explain how a default-deny firewall policy handles traffic.",
            "sample_cryptography_1": "Describe the relationship between encryption and decryption keys in symmetric encryption.",
            "sample_cryptography_2": "Describe the keys used in public-key cryptography.",
            "sample_cryptography_3": "Explain what a digital signature provides and whether it provides confidentiality.",
            "sample_authentication_1": "Explain the difference between authentication and authorization.",
            "sample_authentication_2": "Explain what makes authentication multi-factor and give an example.",
            "sample_authentication_3": "Explain why password storage uses a unique salt.",
        }
        questions = []
        offset = 0
        for kind, count in data["question_counts"].items():
            if count > len(evidence):
                raise ModelError("Sample corpus is too small for this question count; use fewer questions.")
            for index in range(count):
                item = evidence[(offset + index) % len(evidence)]
                fact = item["text"]
                label = f"{item['topic']} (sample section {item['page']})"
                key = {"correct_answer": None, "reference_answer": None, "rubric": [],
                       "explanation": fact, "evidence_ids": [item["chunk_id"]]}
                q = {"type": kind, "text": "", "options": {}, "max_points": 2,
                     "answer_key": key}
                if kind == "multiple_choice":
                    q["text"] = f"Which statement about {label} is supported by the material?"
                    options = [fact, "Security controls eliminate every possible attack.",
                               "Security policies are unnecessary on private networks.",
                               "All network traffic is trustworthy by default."]
                    random.Random(item["chunk_id"]).shuffle(options)
                    q["options"] = dict(zip("ABCD", options))
                    key["correct_answer"] = "ABCD"[options.index(fact)]
                elif kind == "true_false":
                    truth = index % 2 == 0
                    q["text"] = f"True or false: {fact}" if truth else (
                        f"True or false: the material on {label} says security controls "
                        "eliminate every possible attack.")
                    key["correct_answer"] = truth
                else:
                    q["text"] = sample_prompts.get(item["chunk_id"], f"Explain the security concept covered by {label}.")
                    q["max_points"] = 4
                    key["reference_answer"] = fact
                    key["rubric"] = [{"criterion_id": "c1", "concept": fact, "max_points": 4}]
                questions.append(q)
            offset += count
        return {"questions": questions}

    def _grade(self, data):
        words = set(re.findall(r"[a-z]+", data["student_answer"].lower()))
        scores = []
        for criterion in data["rubric"]:
            terms = {w for w in re.findall(r"[a-z]+", criterion["concept"].lower()) if len(w) > 4}
            overlap = len(words & terms) / max(1, len(terms))
            points = round(criterion["max_points"] * overlap)
            scores.append({"criterion_id": criterion["criterion_id"], "points": points})
        return {"criteria_scores": scores,
                "feedback": "Mock keyword-overlap score only; use a real model and reviewed examples for semantic assessment."}
