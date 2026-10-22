"""Micro-lessons: each is ~30 seconds spoken, with one quiz question."""
from __future__ import annotations

LESSONS = [
    {
        "id": "flat-vs-reducing",
        "title": "Flat rate vs reducing rate",
        "body": "A flat rate charges interest on the full amount for the whole loan, even as you pay it back. "
                "A reducing rate charges interest only on what you still owe. "
                "So twelve percent flat costs far more than twelve percent reducing, almost double.",
        "quiz": "Which is cheaper at the same quoted rate: flat or reducing?",
        "answer": "reducing",
    },
    {
        "id": "true-cost",
        "title": "The true cost of a loan",
        "body": "Always ask for the total you will repay, not just the monthly amount. "
                "Fees taken upfront mean you receive less than you borrowed, but you repay the full amount.",
        "quiz": "If you borrow 10,000 and a 500 fee is taken upfront, how much cash do you get?",
        "answer": "9500",
    },
    {
        "id": "emi-limit",
        "title": "How much is too much?",
        "body": "A common warning sign is when all your monthly loan payments add up to more than forty percent of your income. "
                "Keep a cushion for emergencies too.",
        "quiz": "At what share of income do loan payments become a warning sign?",
        "answer": "40",
    },
    {
        "id": "missed-payment",
        "title": "What a missed payment costs",
        "body": "Late fees and extra interest add up fast, and repeated misses can make future loans harder to get. "
                "If you cannot pay, talk to your lender before the due date, not after.",
        "quiz": "When should you talk to your lender if you cannot pay?",
        "answer": "before",
    },
]


def next_lesson(completed: set[str]) -> dict | None:
    for lesson in LESSONS:
        if lesson["id"] not in completed:
            return lesson
    return None
