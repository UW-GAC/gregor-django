Django Allauth Provider for a Drupal \'Simple Oauth\' Site \^\^\^\^\^\^

About

:   Django allauth provider code for logging in via a drupal instance
    that is using the simple_oauth module:
    <https://www.drupal.org/project/simple_oauth>

**Consumer registration (create a Client ID and Secret)**

-   To create a drupal oauth client consumer you need admin privileges
    on the drupal server. If you do not have access, an admin can create
    for you.

-   Create a drupal oauth client ID and secret
    <https://dev.gregorconsortium.org/admin/config/services/consumer>

    -   Click Add Consumer
    -   Label with appropriate label \'Myname Dev Consumer\'
    -   Leave \'User\' blank
    -   Make up your own \'New Secret\', keep track of it, make it
        secure (this is used as your social application secret key)
    -   Is Confidential: \'Yes\'
    -   Is third party: \'No\'
    -   Redirect URI:
        <http://domain.com/accounts/gregor_oauth_provider/login/callback/>

    \- Scopes: click \'Oauth Client User\' only .. warning:: any roles
    selected here are granted automatically to any user who logs in via
    oauth.

    -   Save your Consumer record
    -   Copy the UUID for your newly created consumer (this is used as
        the client_id in your social application)

Development callback URL Notes

:   Use the appropriate domain for your development or production
    server, eg:
    <http://127.0.0.1:8000/accounts/gregor_oauth_provider/login/callback/>
    <http://localhost:8000/accounts/gregor_oauth_provider/login/callback>

Configuration settings:

SCOPES provides a mapping from a drupal machine name to a django group
name. Only scopes where \"request_scope\" is True will be returned from
drupal. The provider processes which scopes were returned from the
drupal provider and adds this data to the logged in users \'Social
Account\' in extra_data. Acting on this data to update user groups
happens outside of this package. For the gregor project there is code in
the SocialAccountAdapter the updates the users groups post login.

``` 
SOCIALACCOUNT_PROVIDERS = {
    "gregor_oauth_provider": {
        "API_URL": "https://dev.gregorconsortium.org",
        "SCOPES": [
            {
                "drupal_machine_name": "oauth_django_access",
                "request_scope": False,
                "django_group_name": "test_django_access",
            },
            {
                "drupal_machine_name": "gregor_anvil_admin",
                "request_scope": True,
                "django_group_name": "gregor_anvil_admin",
            },
        ],
    }
}
```
