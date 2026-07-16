import json
import os

from app import create_app
from app.extensions import db
from app.models import (
    Country,
    CompanySize, BudgetRange,
    AgencyCategory, AgencyScene, Agency,
    News, NewsTag, NewsTagRelation,
)
from app.models.draft import NewsDraft, AgencyDraft

DATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'lexport-frontend', 'docs', 'data.json')

app = create_app(os.environ.get('FLASK_ENV', 'development'))


def seed():
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    with app.app_context():
        # -- Clear in reverse dependency order --
        NewsTagRelation.query.delete()
        News.query.delete()
        NewsTag.query.delete()
        NewsDraft.query.delete()
        AgencyDraft.query.delete()
        Agency.query.delete()
        AgencyScene.query.delete()
        AgencyCategory.query.delete()
        Country.query.delete()
        CompanySize.query.delete()
        BudgetRange.query.delete()
        db.session.commit()

        # -- Insert in FK dependency order --

        # countries
        for item in data['countries']:
            db.session.add(Country(**item))
        db.session.commit()
        print(f'countries: {len(data["countries"])} rows')

        # company_sizes
        for item in data['company_sizes']:
            db.session.add(CompanySize(**item))
        db.session.commit()
        print(f'company_sizes: {len(data["company_sizes"])} rows')

        # budget_ranges
        for item in data['budget_ranges']:
            db.session.add(BudgetRange(**item))
        db.session.commit()
        print(f'budget_ranges: {len(data["budget_ranges"])} rows')

        # agency_categories
        for item in data['agency_categories']:
            db.session.add(AgencyCategory(**item))
        db.session.commit()
        print(f'agency_categories: {len(data["agency_categories"])} rows')

        # agency_scenes
        for item in data['agency_scenes']:
            db.session.add(AgencyScene(**item))
        db.session.commit()
        print(f'agency_scenes: {len(data["agency_scenes"])} rows')

        # agencies
        for item in data['agencies']:
            db.session.add(Agency(**item))
        db.session.commit()
        print(f'agencies: {len(data["agencies"])} rows')

        # news_tags
        for item in data['news_tags']:
            db.session.add(NewsTag(**item))
        db.session.commit()
        print(f'news_tags: {len(data["news_tags"])} rows')

        # news (with FK check for country_id)
        valid_country_ids = {c.id for c in Country.query.all()}
        news_count = 0
        for item in data['news']:
            tag_ids = item.pop('tag_ids', [])
            cid = item.get('country_id')
            if cid is not None and cid not in valid_country_ids:
                print(f'  WARNING: skipping news "{item["title"]}" — unknown country_id "{cid}"')
                continue
            news = News(**item)
            db.session.add(news)
            db.session.commit()
            for tid in tag_ids:
                db.session.add(NewsTagRelation(news_id=news.id, tag_id=tid))
            db.session.commit()
            news_count += 1
        print(f'news: {news_count} rows')

        print('\nSeed complete.')


if __name__ == '__main__':
    seed()
