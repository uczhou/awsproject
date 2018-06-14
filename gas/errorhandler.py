from flask import (abort, flash, redirect, render_template,
  request, session, url_for)

from gas import app, db


"""404 error handler
"""


@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html',
      title='Page not found', alert_level='warning',
      message="The page you tried to reach does not exist. Please check the URL and try again."), 404


"""403 error handler
"""


@app.errorhandler(403)
def forbidden(e):
    return render_template('error.html',
      title='Not authorized', alert_level='danger',
      message="You are not authorized to access this page. If you think you deserve to be granted access, please contact the supreme leader of the mutating genome revolutionary party."), 403


"""405 error handler
"""


@app.errorhandler(405)
def not_allowed(e):
    return render_template('error.html',
      title='Not allowed', alert_level='warning',
      message="You attempted an operation that's not allowed; get your act together, hacker!"), 405


"""500 error handler
"""


@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html',
      title='Server error', alert_level='danger',
      message="The server encountered an error and could not process your request."), 500