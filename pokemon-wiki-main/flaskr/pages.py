from flask import render_template, request, json, flash, abort, redirect, url_for
from .backend import Backend
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField, validators
from .user import User
import flask_login
from flask_login import LoginManager
import base64
import io
from secrets import randbelow
'''This module takes care of rendering pages and page functions.

   Contains all functions in charge of rendering all pages. Calls backend 
   functions to store data in gcp buckets. Takes care of validating user information
   for login and signup. It logsin, signups and logs out users from session. Uploads
   pokemon wiki information to buckets. 
'''
MAX_ID = 386

login_manager = LoginManager(
)  # Lets the app and Flask-Login work together for user loading, login, etc.
backend = Backend()

@login_manager.user_loader
def load_user(username):
    '''Flask function that takes care of loading user to session.
    
       Args:
        username: User username

       Returns:
        User object representing the loaded user.
    '''
    return backend.get_user(username)


def make_endpoints(app):

    class LoginForm(FlaskForm):
        '''Login form, takes two input fields: username and password, has a sumbit field that validates form.'''
        username = StringField('Username', [validators.InputRequired()],
                               render_kw={"placeholder": "Username"})
        password = PasswordField('Password', [validators.InputRequired()],
                                 render_kw={"placeholder": "Password"})
        submit = SubmitField('Login')

    class SignupForm(FlaskForm):
        '''Signup form, takes two input fields: username and password, has a sumbit field that validates form.'''
        username = StringField([validators.InputRequired()],
                               render_kw={"placeholder": "Username"})
        password = PasswordField('Password', [validators.InputRequired()],
                                 render_kw={"placeholder": "Password"})
        submit = SubmitField('Signup')

    # Flask uses the "app.route" decorator to call methods when users
    # go to a specific route on the project's website.
    @app.route("/")
    def home():
        # TODO(Checkpoint Requirement 2 of 3): Change this to use render_template
        # to render main.html on the home page.
        image = backend.get_image('authors/logo.jpg')
        return render_template('main.html', image=image)

    # TODO(Project 1): Implement additional routes according to the project requirements.
    @app.route("/about")
    def about():
        images = [
            backend.get_image('authors/javier.png'),
            backend.get_image('authors/edgar.png'),
            backend.get_image('authors/mark.png')
        ]
        return render_template('about.html', images=images)

    @app.route("/pages", methods=['GET', 'POST'])
    def pages():
        categories = backend.get_categories()
        if request.method == "POST":     
            if request.form["search"] or request.form["sorting"] or request.form.get("type") or request.form.get("region") or request.form.get("nature"):
                name = request.form.get("search")                
                type = request.form.get("type")
                region = request.form.get("region")
                nature = request.form.get("nature")
                sorting = request.form.get("sorting")
                pages = backend.get_pages_using_filter_and_search(name, type, region, nature, sorting)
                return render_template('pages.html', pages=pages, categories=categories)   
            else:
                pages = backend.get_all_page_names()
                return render_template('pages.html', pages=pages, categories=categories)            
        else:
            pages = backend.get_all_page_names()
            return render_template('pages.html', pages=pages, categories=categories)

    @app.route("/pages/<pokemon>")
    def wiki(pokemon="abra"):
        poke_string = backend.get_wiki_page(pokemon)
        # pokemon blob is returned as string, turn into json
        pokemon_data = json.loads(poke_string)
        image = backend.get_image(f'images/{pokemon_data["image-name"]}')
        return render_template("wiki.html", image=image, pokemon=pokemon_data)

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        '''Creates login form and logs in user.

           Creates login form and validates inputs in the form. Calls the backend
           to login the user and checks if the user exists or information is correct.
           Renders login page and form, when logged in successfully it redirects to home page and
           flashes a welcome message. When inputs are not correct it flashes an error message.
           
           Returns:
                Render template function that renders the login page and form.
        '''
        form = LoginForm()

        # User validation
        if form.validate_on_submit():  # Checks if login form is validated

            login_ = backend.sign_in(
                form.username.data,
                form.password.data)  # Calls backend to login in user

            if login_:
                user = User(
                    form.username.data,
                    form.password.data)  # Creates user object to login user
                flask_login.login_user(user)  # Takes care of login in the user
                flash(f'Welcome {flask_login.current_user.username}!')

                return redirect(url_for('home'))
            else:
                flash('Wrong username or password.')

        return render_template('login.html', form=form)  # Renders login page

    @app.route('/signup', methods=['GET', 'POST'])
    def signup():
        '''Creates sign up form and creates a user account.

           Creates sign up form and validates form inputs. Calls backend to sign up 
           the new user. If the user account already exists it flashes an error message.
           If the form is validates it creates the account, flashes a success message and
           redirects the user to login page. Renders signup page and form.

           Returns:
                Render template function that renders signup page and form.
        '''
        form = SignupForm()

        # User validation
        if form.validate_on_submit():  # Checks if signup form is validated

            register = backend.sign_up(
                form.username.data,
                form.password.data)  # Calls backend to create user account

            if register:
                flash('Succesfully created an account.')

                return redirect(
                    url_for('login'))  # When register redirects to login page
            else:
                flash('Account already exists.')

        return render_template('signup.html',
                               form=form)  # Renders signup page and form

    @app.route('/logout', methods=['GET', 'POST'])
    @flask_login.login_required  # Requires the user to be signed in
    def signout():
        '''Signs out user from session and redirects to login page.'''
        flask_login.logout_user()  # Takes care of login out the user
        flash('Logged out successfully.')
        return redirect(url_for('login'))  # Redirects to login page

    @app.route("/upload")
    @flask_login.login_required
    def upload():
        categories = backend.get_categories()
        return render_template("upload.html", categories=categories)

    @app.route("/upload", methods=["POST"])
    def upload_data():
        # dictionary that holds all values from the form, except for the file
        pokemon_data = {
            "name": request.form["name"],
            "type": request.form["type"],
            "region": request.form["region"],
            "nature": request.form["nature"],
            "level": request.form["level"],
            "desc": request.form["desc"],
            "owner": flask_login.current_user.username.capitalize()
        }
        # json object to be uploaded
        file_to_upload = request.files['file']

        # call backend upload
        backend.upload(file_to_upload, pokemon_data)

        # render pages list
        return redirect(url_for('pages'))

    @app.route("/game")
    @flask_login.login_required
    def play_game(pokemon_id=1):
        # make sure pokemon_id has not been guessed before
        seen = backend.get_seen_pokemon(flask_login.current_user.username)
        pokemon_id = randbelow(MAX_ID)
        while str(pokemon_id) in seen:
            pokemon_id = randbelow(MAX_ID)

        # check that image is not a None type
        pokemon_img = None
        while pokemon_img == None:
            pokemon_img = backend.get_pokemon_image(pokemon_id)

        # Get the pokemon and user data
        pokemon_data = backend.get_pokemon_data(pokemon_id)
        user = backend.get_game_user(flask_login.current_user.username)
        pokeball_img = backend.get_pokeball()
        answer = pokemon_data['name']['english']

        # return template
        return render_template("game.html",image=pokemon_img,data=pokemon_data,user=user,pokeball=pokeball_img,answer=answer,seen=seen)


    @app.route("/game",methods=["POST"])
    @flask_login.login_required
    def update_user_and_refresh():
        username = flask_login.current_user.username

        # Get pokemon data
        data = request.form["data"]
        data = data.replace("\'","\"")
        data_json = json.loads(data)

        # Get user guess
        user_guess = request.form["user_guess"]
        user_guess = user_guess.upper()

        # set correct answer and compare to user guess
        correct_answer = data_json["name"]["english"]
        correct_answer = correct_answer.upper()

        # modify and clean up points
        points = int(request.form["points"])
        if user_guess == correct_answer:
            points = points + 100
        elif points - 50 < 0:
            points = 0
        else:
            points = int(points) - 50
        
        # update the seen-pokemon list
        seen = backend.get_seen_pokemon(username)
        seen_id = data_json['id']
        seen_id = str(seen_id)
        seen[seen_id] = True
        backend.update_seen_pokemon(username,seen)

        # update the user with new points and new rank
        backend.update_points(username, points) 
        return redirect(url_for("play_game"))

    @app.route("/leaderboard", methods=["GET"])
    @flask_login.login_required
    def leaderboard():
        '''Displays leaderboard with top 15 users and highlights the current user viewing the leaderboard.'''
        # Get leaderboard list
        leaderboard = backend.get_leaderboard()

        length = len(leaderboard) # Length of the list
        
        # Current user game json data
        curr_user = backend.get_game_user(flask_login.current_user.username)
        
        # If the length is greater than 15 then cut the list to have the top 15 users
        if length > 15:
            leaderboard = leaderboard[:15]

        # Boolean to check if user is in top 15
        user_in_top15 = False if (not curr_user["rank"] or curr_user["rank"] > 15) else True

        trophy = backend.get_image(f'authors/trophy.png') # Image decoration

        return render_template("leaderboard.html", leaderboard=leaderboard, trophy=trophy, curr_user=curr_user, user_in_top15=user_in_top15)
