"""Explicit isolated regression profile; strict tests build separate application settings."""
import os
import tempfile

_regression_db = tempfile.TemporaryDirectory(prefix='miraflores-regression-')
os.environ['WORKPAPER_ENV'] = 'test'
os.environ['WORKPAPER_MODE'] = 'legacy_test'
os.environ['REVIEW_DB_PATH'] = os.path.join(_regression_db.name,'reviews.db')
