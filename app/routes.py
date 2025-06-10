import json
from flask import Blueprint, request, render_template, jsonify, session, redirect, url_for
from urllib.parse import urlparse
import re
import markdown as md
import os
import uuid
from .services import generate_content_bundle_with_avalai, perform_Google_Search, create_word_document, upload_as_google_doc, count_words_fa

main_bp = Blueprint('main', __name__)

temp_article_storage = {}

@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.route('/suggest-headings', methods=['POST'])
def suggest_headings():
    data = request.get_json() or {}
    keyword = data.get('keyword','').strip()
    if not keyword:
        return jsonify({"error": "کلمه کلیدی ارسال نشده است."}), 400

    prompt = (
        f'شما یک استراتژیست ارشد سئو هستید. '
        f'وظیفه شما تولید یک ساختار محتوایی (outline) بهینه شده برای مقاله‌ای '
        f'با کلمه کلیدی "{keyword}" است. خروجی شما باید فقط لیستی از هدینگ‌های '
        f'H2 و H3 باشد، هر یک در یک خط جدید، بدون هیچ متن اضافی.'
    )
    generated = generate_content_bundle_with_avalai(prompt, temperature=0.5)
    if isinstance(generated, dict) and generated.get('error'):
        return jsonify({"error": generated['error']}), 500

    return jsonify({"headings": generated})

@main_bp.route('/generate', methods=['POST'])
def generate_article():
    try:
        # 1) Collect inputs
        title = request.form.get('article_title', '').strip()
        keyword = request.form.get('keyword','').strip()
        secondary = request.form.get('secondary_keywords','').strip()
        word_count = request.form.get('word_count','').strip()
        audience = request.form.get('audience','').strip()
        headings = request.form.get('headings','').strip()
        tone = request.form.get('tone','friendly').strip()
        temp = request.form.get('temperature', type=float) or 0.7
        auto_h = request.form.get('auto_headings')

        # 2) Fetch top-5 competitors
        raw = perform_Google_Search(keyword)
        top_sites = []
        for it in raw:
            link = it.get('link')
            dom  = urlparse(link).netloc if link else ''
            top_sites.append({
                "url": link,
                "title": it.get('title'),
                "domain": dom
            })

        # 3) Prepare competitor info for prompt
        competitor_info = []
        for i, site in enumerate(top_sites, 1):
            competitor_info.append(f"{i}. {site.get('title', '')} ({site.get('url', '')})")
        competitors_str = "\n".join(competitor_info)

        # 4) Structure headings section
        if auto_h:
            struct_instr = (
                f"ساختار مقاله و هدینگ‌ها (H2, H3) را خودت بر اساس تحلیل رقبا و کلمه کلیدی '{keyword}' پیشنهاد بده و پیاده‌سازی کن."
            )
        else:
            full_h = f"H1: {title}\n{headings}"
            struct_instr = f"مقاله باید دقیقاً از این ساختار پیروی کند:\n{full_h}"
        
        wc_instr = f"مقاله باید حدوداً {word_count} کلمه باشد." if word_count.isdigit() else ""
        sec_instr = f'* **کلمات کلیدی فرعی:** "{secondary}" (این کلمات را به صورت طبیعی در متن بگنجان)' if secondary else ""

        # 5) Build new, highly detailed prompt
        prompt = f"""
You are a world-class Persian content writer, native in Farsi, with deep expertise in "{keyword}". You are also a senior SEO strategist and understand how to create high-ranking, human-friendly, Google-compliant content based on EEAT principles (Experience, Expertise, Authoritativeness, Trustworthiness).

## 🎯 Your Goal
Write a long-form, high-value blog post in **Persian** using the information below. Follow all structure, quality, and SEO requirements. Your writing should feel human, expert, and practical.

## 🔹 Topic Information
- **Main Title (H1):** "{title}"
- **Primary Keyword:** "{keyword}"
- **Secondary Keywords:** "{secondary}"
- **Target Audience:** "{audience}" (Write directly to them. Consider their level of knowledge, concerns, and goals.)
- **Tone of Voice:** "{tone}"
- **Minimum Word Count:** {wc_instr} words

✅ This is a **hard minimum** word count. You **must not** write less than this number. Use in-depth explanations, practical examples, how-to steps, comparisons, and FAQs to expand naturally **without fluff**.

## 🔹 Competitor Research
Study these top-ranking pages carefully:
---
{competitors_str}
---
✔ Identify their structure, search intent, and main content themes.
✔ Your content MUST cover all relevant themes they mention — but with **superior depth, clarity, accuracy, and original examples**.
✔ Do NOT copy or paraphrase. Offer a unique, richer perspective.

## 🔹 Structure Instructions
Follow this custom structure exactly:
{struct_instr}

## 🔹 Content Writing Instructions
- **Strong Hook:** Begin with a powerful, engaging introduction (use a question, problem, or shocking stat).
- **High Value in Every Section:** Each paragraph must deliver real, useful, and specific value.
- **Readable Format:** Use short paragraphs (2–4 sentences max). Break up content with headings, lists, and examples. Avoid walls of text.
- **SEO-Friendly Language:** Integrate primary and secondary keywords **naturally**. No keyword stuffing. Prioritize flow and user intent.
- **In-Depth Coverage:** Expand on each point with examples, analogies, and real-world applications. Include clear step-by-step instructions where useful.
- **Natural Flow:** Ensure transitions between sections are logical and smooth.
- **Avoid AI Detection:** Make the content feel fully human by varying sentence structures, using idioms or metaphors, and avoiding generic patterns.
- **You are given a required structure via {struct_instr}. You MUST:
- **Fully write each section based on the provided titles/headings.
- **Do NOT skip or shorten any section.
- **Do NOT simply list the structure — write full, practical, detailed content under each.
- **This structure is mandatory and guides the full flow of your Persian article.


## 🔹 Output Format
Return a clean JSON object with the following fields — **all content in Persian**:

## 6. Required JSON Output (Output must be in PERSIAN)
Your entire response must be a single JSON object. All string values within the JSON (like meta descriptions and the blog post) **must be written in Persian**.
```json
{{
  "meta_descriptions": [
    "یک متا دیسکریپشن جذاب و دعوت کننده به اقدام (حدود ۱۵۵ کاراکتر) که شامل کلمه کلیدی اصلی باشد.",
    "یک نسخه متفاوت از متا دیسکریپشن برای تست A/B."
  ],
  "blog_post_markdown": "## {title}\\n\\nمتن کامل و با کیفیت مقاله شما در فرمت مارک‌داون اینجا قرار می‌گیرد. تمام دستورالعمل‌های بالا باید در این متن رعایت شده باشد و خروجی کاملا به زبان فارسی باشد.",
  "image_prompts": [
    "A descriptive prompt in English for creating an engaging Hero Image for the article.",
    "A concept in English for an infographic or diagram to be used within the article's body."
  ]
}}
"""
        # 4) Call AI, expect a JSON response
        raw_response = generate_content_bundle_with_avalai(prompt, temp, expect_json=True)
        if isinstance(raw_response, dict) and raw_response.get('error'):
            raise Exception(raw_response['error'])

        # 5) Try to extract pure JSON from any extra text
        m = re.search(r'```json\n(.*?)\n```', raw_response, flags=re.DOTALL)
        if m:
            json_string = m.group(1).strip()
        else:
            # Fallback if the above pattern doesn't match (e.g., if AI doesn't wrap in ```json```)
            m = re.search(r'\{.*\}', raw_response, flags=re.DOTALL)
            if m:
                json_string = m.group(0).strip()
            else:
                raise Exception("پاسخ مدل JSON نبود.")

        try:
            result_json = json.loads(json_string)
        except json.JSONDecodeError as e:
            print(f"--- DEBUG: JSON Decode Error: {e}")
            print(f"--- DEBUG: Malformed JSON string: {json_string}")
            raise Exception(f"خطا در تفسیر پاسخ JSON مدل: {e}")

        # 6) Pull pieces out
        meta_descs    = result_json.get('meta_descriptions', [])
        blog_md       = result_json.get('blog_post_markdown', '')
        image_prompts = result_json.get('image_prompts', [])

        # 7) Convert Markdown to HTML
        article_html = md.markdown(
            blog_md,
            extensions=['fenced_code', 'tables', 'nl2br']
        )

        # 8) Create .docx file & upload to Google Drive
        docx_file = create_word_document(blog_md, title)
        google_id = upload_as_google_doc(docx_file, title, os.getenv('GOOGLE_DRIVE_FOLDER_ID')) # Using os.getenv

        # 9) Word count
        wc = count_words_fa(blog_md)

        # Store article_html temporarily and get a unique ID
        article_id = str(uuid.uuid4())
        temp_article_storage[article_id] = article_html

        # 10) Store data in session and redirect
        session['article_data'] = {
            'meta_descriptions': meta_descs,
            'image_prompts': image_prompts,
            'top_sites': top_sites,
            'article_id': article_id, # Store ID instead of full HTML
            'wordcount': wc,
            'google_doc_id': google_id,
            'error': None
        }
        return redirect(url_for('main.article_result'))

    except Exception as e:
        # on error, store error in session and redirect
        session['article_data'] = {
            'meta_descriptions': [],
            'image_prompts': [],
            'top_sites': [],
            'article_id': None, # No article ID on error
            'wordcount': 0,
            'google_doc_id': None,
            'error': str(e)
        }
        return redirect(url_for('main.article_result'))

@main_bp.route('/article_result')
def article_result():
    article_data = session.get('article_data', None)
    if not article_data:
        # If no data in session, redirect to home or show an error
        return redirect(url_for('main.index'))

    # Retrieve article_html from temporary storage using the ID
    article_html = ""
    if article_data.get('article_id'):
        article_html = temp_article_storage.pop(article_data['article_id'], "") # Pop to remove after use

    return render_template(
        'result.html',
        meta_descriptions=article_data['meta_descriptions'],
        image_prompts=article_data['image_prompts'],
        top_sites=article_data['top_sites'],
        article_html=article_html, # Pass retrieved HTML to template
        wordcount=article_data['wordcount'],
        google_doc_id=article_data['google_doc_id'],
        error=article_data['error']
    )

@main_bp.route('/brief')
def content_brief_page():
    """Renders the content brief input form."""
    return render_template('brief.html')

@main_bp.route('/generate-brief', methods=['POST'])
def generate_brief():
    """Generates a full content brief based on a keyword."""
    try:
        keyword = request.form.get('keyword', '').strip()
        if not keyword:
            raise ValueError("کلمه کلیدی ارسال نشده است.")

        json_structure = {
        "search_intent": "اینجا نیت جستجوی کاربر را توضیح دهید (مثلاً: اطلاعاتی، تجاری، مقایسه‌ای و ...).",
        "target_audience": "مخاطب هدف این کلمه کلیدی را با جزئیات توصیف کنید (مثلا: بازیکنان مبتدی پابجی، دانشجویان برنامه‌نویسی، مدیران بازاریابی).",
        "catchy_titles": [
            "یک عنوان جذاب و قلاب دار که کنجکاوی را برانگیزد",
            "یک عنوان دیگر به سبک لیست (مثلا: ۷ راه برای...)",
            "عنوان سوم که یک مزیت کلیدی را نشان دهد",
            "عنوان چهارم به شکل سوالی",
            "عنوان پنجم کوتاه و مستقیم"
        ],
        "content_structure": [
            "H2: مقدمه‌ای جذاب",
            "H3: چرا این موضوع مهم است؟",
            "H2: بخش اصلی اول",
            "H2: نتیجه‌گیری و جمع‌بندی"
        ],
        "key_elements": [
            "به این نکته کلیدی حتما اشاره شود.",
            "یک مثال عملی از موضوع ارائه گردد.",
            "استفاده از آمار و ارقام معتبر برای اعتباربخشی به محتوا."
        ],
        "keywords": {
            "primary": keyword,  # کلمه کلیدی مستقیم اینجا قرار میگیرد
            "secondary": ["کلمه کلیدی فرعی ۱", "کلمه کلیدی lsi", "مترادف کلیدواژه اصلی"]
        },
        "seo_tips": [
            "یک نکته مهم برای سئو داخلی (On-Page) مرتبط با این کلمه کلیدی.",
            "یک پیشنهاد برای لینک سازی داخلی (Internal Linking) به صفحات مرتبط.",
            "یک نکته در مورد استفاده از داده‌های ساختار یافته (Schema Markup) مناسب."
        ],
        "faq": [
            { "question": "اولین سوال متداول و مهم در مورد کلیدواژه", "answer": "پاسخ کامل و دقیق به سوال اول." },
            { "question": "دومین سوال متداول و پرتکرار", "answer": "پاسخ کامل و دقیق به سوال دوم." },
            { "question": "سومین سوال متداول", "answer": "پاسخ کامل و دقیق به سوال سوم." }
        ],
        "cta_suggestions": [
            "دعوت به ثبت‌نام در وبینار مرتبط.",
            "تشویق کاربر به گذاشتن کامنت و پرسیدن سوال."
        ]
        }
        json_example_string = json.dumps(json_structure, indent=2, ensure_ascii=False)

        prompt = f"""
شما یک استراتژیست ارشد سئو و محتوا هستید.
وظیفه شما تولید یک بریف محتوایی کامل و دقیق برای کلمه کلیدی اصلی "{keyword}" است.
خروجی شما باید فقط یک آبجکت JSON با ساختار مشخص زیر باشد و هیچ متن اضافی نداشته باشد.

{json_example_string}
"""

        raw_response = generate_content_bundle_with_avalai(prompt, 0.5, expect_json=True)
        if isinstance(raw_response, dict) and raw_response.get('error'):
            raise Exception(raw_response['error'])

        m = re.search(r'\{.*\}', raw_response, flags=re.DOTALL)
        if not m:
            raise Exception("پاسخ مدل، ساختار JSON معتبری نداشت.")
        
        result_json = json.loads(m.group(0))

        return render_template(
            'brief_result.html',
            brief=result_json,
            keyword=keyword,
            error=None
        )

    except Exception as e:
        return render_template(
            'brief_result.html',
            brief=None,
            keyword=request.form.get('keyword', ''),
            error=str(e)
        ) 