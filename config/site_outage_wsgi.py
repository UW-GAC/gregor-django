# Simple WSGI application to serve a maintenance page
# Useful when you need to completely stop the django site
# To use, copy into place where your django wsgi application
#   file is located. eg: config/gregor_apps_wsgi.py


def application(environ, start_response):
    status = "200 OK"
    response_headers = [("Content-type", "text/html")]
    start_response(status, response_headers)

    maintenance_html = """
    <!DOCTYPE html>
    <html>
    <head><title>Site Maintenance</title></head>
    <body>
        <h1>Site Maintenance</h1>
        <p>The GREGoR AnVIL application website is currently down for maintenance</p>
    </body>
    </html>
    """

    return [maintenance_html.encode("utf-8")]
