# מדריך למדריך: Anthropic Prompt Engineering Interactive Tutorial

המדריך הרשמי של Anthropic הוא 9 מחברות Jupyter עם תרגילים ומפתח תשובות:
https://github.com/anthropics/prompt-eng-interactive-tutorial

הוא נכתב ל-Claude 3 Haiku, ולכן חלקים ממנו כבר לא מתאימים למודלים של 2026.
הרשימה למטה אומרת מה לקרוא, מה לדלג, ומה לעשות אחרת.

## הכנה

```bash
git clone https://github.com/anthropics/prompt-eng-interactive-tutorial
cd prompt-eng-interactive-tutorial/Anthropic\ 1P
pip install anthropic jupyter
jupyter notebook
```

במחברת 00 (Tutorial How-To) החלף את שם המודל ל-`claude-haiku-4-5`.
הוא זול, עדיין תומך ב-prefill וב-temperature, ולכן כל התרגילים ירוצו כמו שנכתבו.
אם תשתמש במודל 4.6 ומעלה, תרגילי ה-prefill יחזירו שגיאת 400.

## מה לעשות בכל פרק

- **פרק 1, Basic Prompt Structure: לעבור מהר.** מבנה ה-Messages API; תכיר אותו לעומק בנושא 2.
- **פרק 2, Being Clear and Direct: חובה.** העיקרון החשוב ביותר, ותקף גם היום.
- **פרק 3, Assigning Roles: חובה.** משלים את פרק role prompting בשיעור.
- **פרק 4, Separating Data and Instructions: חובה.** הבסיס להגנה מ-prompt injection (תרגיל 5).
- **פרק 5, Formatting Output and Speaking for Claude: חלקית.** החלק על prefill מיושן: במודלים החדשים משתמשים ב-structured outputs (נושא 3).
- **פרק 6, Precognition (Thinking Step by Step): חלקית.** המודלים החדשים חושבים בעצמם (adaptive thinking + effort). קרא כדי להבין את הרעיון, אל תתרגל.
- **פרק 7, Using Examples: חובה.** משלים את תרגיל 6.
- **פרק 8, Avoiding Hallucinations: חובה.** "תן למודל דרך להגיד שהוא לא יודע", בדיוק תרגיל 4.
- **פרק 9, Complex Prompts from Scratch: מומלץ.** 4 דוגמאות מתעשיות שונות; טוב לסיכום.
- **Appendix, Chaining, Tool Use, Search: לדלג כרגע.** כל אחד מהם מקבל נושא משלו בהמשך הקורס.

זמן משוער לפרקי החובה: כשעה וחצי. אפשר לפצל על פני השבוע.
