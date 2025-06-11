import os
import json
import uuid
from urllib.parse import urlparse

import markdown as md
from flask import (
    Blueprint, request, render_template,
    jsonify, session, redirect, url_for
)

from .services import (
    generate_content_bundle_with_llm,  # now sync
    perform_Google_Search,
    create_word_document,
    upload_as_google_doc,
    count_words_fa,
    get_kwrank_keyword_suggestions
)
from .utils import load_prompt_template

main_bp = Blueprint('main', __name__)
temp_article_storage = {}

@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.route('/article_generator')
def article_generator_page():
    return render_template('article_generator.html')

@main_bp.route('/keyword_suggester')
def keyword_suggester_page():
    return render_template('keyword_suggester.html')

@main_bp.route('/get-keyword-suggestions', methods=['POST'])
def get_keyword_suggestions():
    data = request.form
    keyword = data.get('keyword', '').strip()
    if not keyword:
        return jsonify({"error": "کلمه کلیدی ارسال نشده است.", "status": 400}), 400

    result = get_kwrank_keyword_suggestions(keyword)
    return jsonify(result), result.get('status', 200)

@main_bp.route('/suggest-headings', methods=['POST'])
def suggest_headings():
    data    = request.get_json() or {}
    keyword = data.get('keyword', '').strip()
    if not keyword:
        return jsonify({"error": "کلمه کلیدی ارسال نشده است."}), 400

    prompt    = load_prompt_template("suggest_headings_prompt.txt").format(keyword=keyword)
    # call synchronously
    generated = generate_content_bundle_with_llm(prompt, temperature=0.5)
    if isinstance(generated, dict) and generated.get('error'):
        return jsonify({"error": generated['error']}), 500

    return jsonify({"headings": generated})

@main_bp.route('/generate', methods=['POST'])
def generate_article():
    try:
        # 1) Collect inputs
        title      = request.form.get('article_title', '').strip()
        keyword    = request.form.get('keyword', '').strip()
        secondary  = request.form.get('secondary_keywords', '').strip()
        word_count = request.form.get('word_count', '').strip()
        audience   = request.form.get('audience', '').strip()
        headings   = request.form.get('headings', '').strip()
        tone       = request.form.get('tone', 'friendly').strip()
        temp       = request.form.get('temperature', type=float) or 0.7
        auto_h     = request.form.get('auto_headings')

        # 2) Fetch top-5 competitors
        raw = perform_Google_Search(keyword)
        top_sites = []
        for it in raw:
            link = it.get('link')
            dom  = urlparse(link).netloc if link else ''
            top_sites.append({
                "url":    link,
                "title":  it.get('title', ''),
                "domain": dom
            })

        # 3) Prepare competitor info for prompt
        competitor_info = [
            f"{i}. {site['title']} ({site['url']})"
            for i, site in enumerate(top_sites, start=1)
        ]
        competitors_str = "\n".join(competitor_info)

        # 4) Structure headings section
        if auto_h:
            struct_instr = (
                f"ساختار مقاله و هدینگ‌ها (H2, H3) را خودت بر اساس تحلیل رقبا و "
                f"کلمه کلیدی '{keyword}' پیشنهاد بده و پیاده‌سازی کن."
            )
        else:
            full_h = f"H1: {title}\n{headings}"
            struct_instr = f"مقاله باید دقیقاً از این ساختار پیروی کند:\n{full_h}"

        wc_instr  = f"مقاله باید حدوداً {word_count} کلمه باشد." if word_count.isdigit() else ""
        sec_instr = (
            f'* **کلمات کلیدی فرعی:** "{secondary}" '
            f'(این کلمات را به صورت طبیعی در متن بگنجان)'
        ) if secondary else ""

        # 5) Build prompt
        prompt_template = load_prompt_template("generate_article_prompt.txt")
        prompt = prompt_template.format(
            keyword=keyword,
            title=title,
            secondary=secondary,
            audience=audience,
            tone=tone,
            wc_instr=wc_instr,
            competitors_str=competitors_str,
            struct_instr=struct_instr
        )

        # 6) Call AI synchronously
        result_json = generate_content_bundle_with_llm(prompt, temp, expect_json=True)
        if isinstance(result_json, dict) and result_json.get('error'):
            raise Exception(result_json['error'])

        # 7) Unpack
        meta_descs    = result_json.get('meta_descriptions', [])
        blog_md       = result_json.get('blog_post_markdown', '')
        image_prompts = result_json.get('image_prompts', [])

        # 8) Convert Markdown → HTML
        article_html = md.markdown(blog_md, extensions=['fenced_code', 'tables', 'nl2br'])

        # 9) Create .docx and upload
        docx_file = create_word_document(blog_md, title)
        google_id = upload_as_google_doc(docx_file, title, os.getenv('GOOGLE_DRIVE_FOLDER_ID'))

        # 10) Word count
        wc = count_words_fa(blog_md)

        # 11) Temp store & session
        article_id = str(uuid.uuid4())
        temp_article_storage[article_id] = article_html
        session['article_data'] = {
            'meta_descriptions': meta_descs,
            'image_prompts':     image_prompts,
            'top_sites':         top_sites,
            'article_id':        article_id,
            'wordcount':         wc,
            'google_doc_id':     google_id,
            'error':             None
        }

        return redirect(url_for('main.article_result'))

    except Exception as e:
        session['article_data'] = {
            'meta_descriptions': [],
            'image_prompts':     [],
            'top_sites':         [],
            'article_id':        None,
            'wordcount':         0,
            'google_doc_id':     None,
            'error':             str(e)
        }
        return redirect(url_for('main.article_result'))

@main_bp.route('/article_result')
def article_result():
    data = session.get('article_data')
    if not data:
        return redirect(url_for('main.index'))

    html = ""
    if data.get('article_id'):
        html = temp_article_storage.pop(data['article_id'], "")

    return render_template(
        'article_result.html',
        meta_descriptions=data['meta_descriptions'],
        image_prompts=    data['image_prompts'],
        top_sites=        data['top_sites'],
        article_html=     html,
        wordcount=        data['wordcount'],
        google_doc_id=    data['google_doc_id'],
        error=            data['error']
    )

@main_bp.route('/brief')
def content_brief_page():
    return render_template('brief.html')

@main_bp.route('/generate-brief', methods=['POST'])
def generate_brief():
    try:
        keyword = request.form.get('keyword', '').strip()
        if not keyword:
            raise ValueError("کلمه کلیدی ارسال نشده است.")

        prompt_template = load_prompt_template("generate_brief_prompt.txt")
        prompt = prompt_template.format(keyword=keyword)

        brief_json = generate_content_bundle_with_llm(prompt, 0.5, expect_json=True)
        if isinstance(brief_json, dict) and brief_json.get('error'):
            raise Exception(brief_json['error'])

        session['brief_data'] = {'brief': brief_json, 'error': None, 'keyword': keyword}
        return redirect(url_for('main.brief_result'))

    except Exception as e:
        session['brief_data'] = {'brief': {}, 'error': str(e)}
        return redirect(url_for('main.brief_result'))

@main_bp.route('/brief_result')
def brief_result():
    brief_data = session.get('brief_data')
    if not brief_data:
        return redirect(url_for('main.brief'))
    return render_template(
        'brief_result.html',
        brief=brief_data['brief'],
        error=brief_data['error'],
        keyword=brief_data.get('keyword', '')
    )