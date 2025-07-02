import logging
import re
from datetime import datetime
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request
from flask_cors import CORS
from transformers import pipeline

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

try:
    classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
    sentiment_analyzer = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")
    logging.info("AI models loaded successfully.")
except Exception as e:
    logging.error(f"Error loading AI models: {e}")
    classifier = None
    sentiment_analyzer = None

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',  
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Connection': 'keep-alive',
}




def scrape_github_users(keyword, location, per_page=10):
    query = f"{keyword} location:{location}"
    url = f"https://api.github.com/search/users?q={query}&per_page={per_page}"
    headers = {
"Accept": "application/vnd.github+json",
"User-Agent": "LeadFinderBot/1.0"
                }
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json()
    users = []
    for item in data.get("items", []):
        users.append({
            "username": item["login"],
            "profile_url": item["html_url"],
            "bio": "", 
            })
    return users


try:
    summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6")
    logging.info("Summarizer model loaded successfully.")
except Exception as e:
    logging.warning("Summarizer model failed to load.")
    summarizer = None

def summarize_top_project(username):

    try:
        repo_url = f"https://github.com/{username}?tab=repositories"
        response = requests.get(repo_url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        repos = soup.select("li[itemprop='owns']")
        top_repo = None
        top_stars = 0

        for repo in repos:
            name_tag = repo.select_one("a[itemprop='name codeRepository']")
            stars_tag = repo.select_one("a[href$='/stargazers']")

            if name_tag:
                repo_name = name_tag.get_text(strip=True)
                stars_text = stars_tag.get_text(strip=True) if stars_tag else "0"
                stars = int(float(stars_text.replace('k', '000').replace(',', '')) if 'k' in stars_text else re.sub(r'\D', '', stars_text) or 0)

                if stars > top_stars:
                    top_repo = repo_name
        
                    top_stars = stars

        if not top_repo:
            return "No standout public project found."

        readme_url = f"https://raw.githubusercontent.com/{username}/{top_repo}/main/README.md"
        readme = requests.get(readme_url, timeout=5)
        if readme.status_code != 200 or len(readme.text) < 100:
            return f"{top_repo}: No detailed README available."
        if summarizer:
            summary = summarizer(readme.text[:1000], max_length=60, min_length=25, do_sample=False)[0]['summary_text']
            return f"{top_repo}: {summary}"
        else:
            return f"{top_repo}: {readme.text[:150]}..."
    except Exception as e:
        logging.warning(f"Could not summarize top project for {username}: {e}")
        return "Could not summarize top project."

def enrich_github_profile(profile_url):
    try:
        response = requests.get(profile_url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        followers_tag = soup.find('a', href=re.compile(r'\?tab=followers'))
        repos_tag = soup.find('a', href=re.compile(r'\?tab=repositories'))
        
        
        followers = followers_tag.find('span').get_text(strip=True) if followers_tag and followers_tag.find('span') else "0"
        repos = repos_tag.find('span').get_text(strip=True) if repos_tag and repos_tag.find('span') else "0"
        
    
        followers_val = int(float(followers.replace('k', '')) * 1000) if 'k' in followers.lower() else int(re.sub(r'\D', '', followers))
        repos_val = int(float(repos.replace('k', '')) * 1000) if 'k' in repos.lower() else int(re.sub(r'\D', '', repos))

        return {'followers': followers_val, 'repositories': repos_val}
    except Exception as e:
        logging.error(f"Failed to enrich profile {profile_url}: {e}")
        return {'followers': 0, 'repositories': 0}

def calculate_candidate_score(profile_data):
    """
    Calculates a "Candidate Score" out of 100 based on a heuristic combining
    profile metrics and AI analysis of their bio.
    """
    score = 0
    score += min(profile_data['followers'] / 10, 25)  
    score += min(profile_data['repositories'] / 2, 25) 

    if profile_data['bio'] and sentiment_analyzer:
        tech_keywords = ['engineer', 'developer', 'python', 'javascript', 'react', 'node', 'data', 'cloud', 'ai', 'ml']
        keyword_hits = sum([1 for k in tech_keywords if k in profile_data['bio'].lower()])
        score += min(keyword_hits * 5, 25) 
        
        
        sentiment = sentiment_analyzer(profile_data['bio'])[0]
        if sentiment['label'] == 'POSITIVE':
            score += int(sentiment['score'] * 25) 

    return min(int(score), 100) 

@app.route('/api/find-people', methods=['POST'])
def find_people_endpoint():
    """ API endpoint for recruiters to find candidates. """
    data = request.get_json()
    keyword = data.get('keyword')
    location = data.get('location')

    if not keyword or not location:
        return jsonify({"error": "Missing keyword or location"}), 400

    initial_users = scrape_github_users(keyword, location)
    enriched_users = []
    
    for user in initial_users:
        details = enrich_github_profile(user['profile_url'])
        user.update(details)
        score = calculate_candidate_score(user)
        enriched_users.append({
            "Candidate Score": score,
            "Username": user['username'],
            "Bio": summarize_top_project(user['username']),
            "Profile URL": user['profile_url'],
            "Followers": user['followers'],
            "Repositories": user['repositories']
        })
    
    sorted_users = sorted(enriched_users, key=lambda x: x['Candidate Score'], reverse=True)
    return jsonify(sorted_users)



HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en-US,en;q=0.9",
}

def get_company_news(company_url):
    try:
        response = requests.get(company_url, headers=HEADERS, timeout=5)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        news_keywords = ['news', 'blog', 'press', 'insights', 'media']
        news_link = None
        for keyword in news_keywords:
            tag = soup.find('a', href=re.compile(keyword, re.IGNORECASE))
            if tag:
                news_link = urljoin(company_url, tag['href'])
                break

        if not news_link:
            return "No news page found", ""

        news_response = requests.get(news_link, headers=HEADERS, timeout=5)
        news_response.raise_for_status()
        news_soup = BeautifulSoup(news_response.text, 'html.parser')

        headlines = [tag.get_text(strip=True) for tag in news_soup.find_all(['h1', 'h2', 'h3'])[:5]]
        return " ".join(headlines), news_link
    except:
        return "Could not access website", ""

def classify_insight(text):
    if not text or text in ["No news page found", "Could not access website"]:
        return "N/A", 0.0
    candidate_labels = [
        "Company Growth and Expansion",
        "New Product or Feature Launch",
        "Major Partnership Announcement",
        "Secured New Funding",
        "Leadership Team Change",
        "Industry Report or Analysis"
    ]
    result = classifier(text, candidate_labels)
    return result['labels'][0], result['scores'][0]

def calculate_company_score(insight, confidence, num_jobs):
    score = 0
    base_score = {
        "Secured New Funding": 70,
        "Major Partnership Announcement": 50,
        "New Product or Feature Launch": 40,
        "Company Growth and Expansion": 30,
    }.get(insight, 0)

    score += int(base_score * (0.5 + confidence * 0.5)) 
    score += min(num_jobs * 3, 30) 
    return min(score, 100)

def calculate_likelihood_to_hire(momentum_score, num_jobs):
    velocity = min(num_jobs * 10, 70)
    momentum_component = (momentum_score / 100) * 30
    return min(int(velocity + momentum_component), 100)

def find_company_linkedin_url(company_name):
    if not company_name or company_name == "Unknown":
        return None

    query = f'"{company_name}" LinkedIn company profile'
    url = f"https://duckduckgo.com/html/?q={requests.utils.quote(query)}"

    try:
        response = requests.get(url, headers=HEADERS, timeout=5)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        for link in soup.select('.result__a'):
            href = link.get('href', '')
            if 'linkedin.com/company/' in href and '/posts/' not in href and '/jobs/' not in href:
                return href.split('?')[0]
        return None
    except:
        return None

classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
sentiment = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")

HEADERS = {
   'User-Agent': 'Mozilla/5.0',
   'Accept-Language': 'en-US,en;q=0.9'
}

def get_jobs_from_jobicy_api(keyword):
    url = f"https://jobicy.com/api/v2/remote-jobs?count=50&tag={keyword}"
    logging.info(f"[Jobicy] Fetching: {url}")
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    jobs = resp.json().get("jobs", [])[:50]
    return [{
        "job_title": j.get("jobTitle","N/A"),
        "company_name": j.get("companyName","N/A"),
        "job_description": j.get("description",""),
        "job_url": j.get("url")
    } for j in jobs]

def classify_roles(text):
    labels = ["hiring ramp", "remote friendly", "fast-growing", "startup culture", "enterprise", "AI related"]
    out = classifier(text, labels)
    return dict(zip(out["labels"], out["scores"]))

def analyze_sentiment(text):
    out = sentiment(text[:512])[0]
    return out["label"], out["score"]

def calculate_scores(company_name, listings):
    num = len(listings)
    desc = " ".join([j["job_title"]+" "+j["job_description"] for j in listings])
    topics = classify_roles(desc)
    sentiment_label, sent_score = analyze_sentiment(desc)

    momentum = (
        topics.get("hiring ramp", 0)*25 +
        topics.get("fast-growing",0)*20 +
        topics.get("AI related",0)*15 +
        (sent_score if sentiment_label=="POSITIVE" else -sent_score)*10
    )
    momentum = max(min(int(momentum), 100), 0)

    urgency = min(num * 15, 100)

    return momentum, urgency

from flask import request, jsonify
import re
import logging
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup
@app.route('/api/find-companies', methods=['POST'])
def find_companies():
    data = request.get_json()
    keyword = data.get('keyword')
    location = data.get('location')  

    if not keyword:
        return jsonify({"error": "Keyword is required"}), 400

    job_listings = get_jobs_from_jobicy_api(keyword)
    if not job_listings:
        return jsonify([])

    companies = {}
    for job in job_listings:
        name = job.get('company_name', 'Unknown')
        if name not in companies:
            companies[name] = {
                'job_titles': [],
                'job_urls': [],
                'company_logo': job.get('company_logo'),  
                'count': 0
            }
        companies[name]['job_titles'].append(job.get('job_title', 'N/A'))
        companies[name]['job_urls'].append(job.get('job_url'))
        companies[name]['count'] += 1

 
    enriched_companies = []
    for name, data in companies.items():
        num_jobs = data['count']
        website_guess = f"https://www.{re.sub(r'[^a-zA-Z0-9]', '', name.lower())}.com"
        linkedin_url = find_company_linkedin_url(name)

        news_text, _ = get_company_news(website_guess)
        insight, confidence = classify_insight(news_text)
        momentum_score = calculate_company_score(insight, confidence, num_jobs)
        likelihood_score = calculate_likelihood_to_hire(momentum_score, num_jobs)

        enriched_companies.append({
            "Company": name,
            "Company Logo": data['company_logo'],
            "Website": website_guess,
            "LinkedIn URL": linkedin_url,
            "Hiring Velocity": f"{num_jobs} open role(s)",
            "Sample Job": data['job_titles'][0],
            "Job URL": data['job_urls'][0],
            "Key Insight": insight,
            "Company Score": momentum_score,
            "Likelihood to Hire": likelihood_score
        })

    sorted_companies = sorted(enriched_companies, key=lambda x: x['Likelihood to Hire'], reverse=True)
    return jsonify(sorted_companies[:20])

if __name__ == '__main__':
    app.run(debug=True, port=5000)