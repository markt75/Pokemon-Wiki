"""This module contains the backend of the pokemon wiki which interacts with the Google Cloud Storage.
The backend retrieves user generated pages and image data from the cloud, creates username and password blobs, creates hashed passwords,
compares username and password blobs for logging in, and uploads user generated page data to the cloud.

Typical Usage:
backend = Backend()
data = backend.get_wiki_page('charmander')
pages = backend.get_all_page_names()
backend.upload('charmander.png', pokemon_dictionary)
signup = backend.sign_up('javier', 'pokemon123')
login = backend.sign_in('javier', 'pokemon123')
image = get_image('pokemon/charmander')
"""

from google.cloud import storage
import base64
import hashlib
from flask import json, render_template, flash, redirect, url_for
from .user import User
from secrets import randbelow

MAX_ID = 386

class Backend:

    def __init__(self,
                 client=storage.Client(),
                 hashfunc=hashlib,
                 base64func=base64,
                 json=json):
        """
        Args:
            client: Dependency injection for mocking the cloud storage client.
            hashfunc: Dependency injection for mocking the hashlib module.
            base64func: Dependency injection for mocking the base64 module.
            json: Dependency injection for mocking the json module.
        """
        self.client = client
        self.hashfunc = hashfunc
        self.base64func = base64func
        self.json = json

    def get_wiki_page(self, name):
        """ Retrieves user generated page from cloud storage and returns it.
        Args:
            name: The name of the user generated page to retrieve from the cloud.
        Returns:
            content: The user generated page data.
        """
        bucket = self.client.get_bucket('wiki-content-techx')
        blob = bucket.get_blob(f'pages/{name}')

        # reading json object blob and returning its contents
        with blob.open('r') as f:
            content = f.read()
        return content

    def get_all_page_names(self):
        """ Retrieves the names of all user generated pages and returns a list containing them.
        Returns:
            page_names: List that contains all user generated page names as strings.
        """
        bucket = self.client.get_bucket('wiki-content-techx')
        blobs = bucket.list_blobs(prefix='pages/')
        page_names = []

        # adding every blob to page_names except the first blob since it's just the folder name
        for index, blob in enumerate(blobs):
            if index == 0:
                continue
            page_names.append(blob.name)
        return page_names

    def upload(self, file, pokemon_data):
        """ Uploads image data and user generated page data to the cloud storage.
        Args:
            file: The image file uploaded by the user.
            pokemon_data: A dictionary with all data associated with user generated page.
        """
        bucket = self.client.get_bucket('wiki-content-techx')

        path = 'pages/' + pokemon_data["name"].lower()
        blob = bucket.get_blob(path)

        if not blob:
            # uploading user image of pokemon to the images blob
            images = bucket.blob(f'images/{file.filename}')
            images.upload_from_file(file)

            # adding image name to pokemon dictionary
            pokemon_data["image-name"] = file.filename

            # adding image type (jpg, png, etc) to pokemon dictionary
            pokemon_data["image-type"] = file.content_type

            # converting pokemon dictionary to json object
            json_obj = self.json.dumps(pokemon_data)

            # uploading a json object to the new pages blob
            blob = bucket.blob(path)
            blob.upload_from_string(data=json_obj,
                                    content_type="application/json")

            return True

        return False

    def sign_up(self, username, password):
        """ Uploads user account information to the cloud storage if account doesn't already exist.
            Creates a hashed password from user password and uploads new password to cloud storage.
        Args:
            username: The username that the user inputs.
            password: The password that the user inputs.
        """
        bucket = self.client.get_bucket('users-passwords-techx')

        game_users_bucket = self.client.get_bucket('wiki-content-techx')
        path = f'user_game_ranking/game_users/{username}'

        # if an account with that username already exists we shouldn't be creating a new one
        if bucket.get_blob(username):
            return False
        else:
            blob = bucket.blob(username)

            # salting the password with username and a secret word
            salt = f"{username}jmepokemon{password}"
            # generating hashed password after the salting
            hashed_password = self.hashfunc.blake2b(salt.encode()).hexdigest()

            # writing hashed password to the new user blob we created
            with blob.open('w') as f:
                f.write(hashed_password)

            # Adds new user to the ranking blob
            game_blob = game_users_bucket.blob(path)
            json_obj = {"name": username, "points": 0, "rank": None}
            json_str = self.json.dumps(json_obj)
            game_blob.upload_from_string(data=json_str,
                                         content_type="application/json")

            # Adds new user to the seen blob
            seen_path = f'user_game_ranking/seen/{username}'
            seen_blob = game_users_bucket.blob(seen_path)
            seen_json = {} # empty because a new user has not encountered any yet
            seen_str = self.json.dumps(seen_json)
            seen_blob.upload_from_string(data=seen_str,content_type="application/json")

            return True

    def sign_in(self, username, password):
        """ Checks whether specific account information exists in the cloud storage.
            Creates a hashed password from user password and compares it with the hashed 
            password associated with the username if it exists.
        Args:
            username: The username that the user inputs.
            password: The password that the user inputs.
        """
        bucket = self.client.get_bucket('users-passwords-techx')
        blob = bucket.get_blob(username)

        if blob:
            # salting the password with username and a secret word
            salt = f"{username}jmepokemon{password}"
            # generating hashed password after the salting
            hashed_password = self.hashfunc.blake2b(salt.encode()).hexdigest()

            # reading hashed password from the username
            with blob.open('r') as f:
                content = f.read()
            # checking whether the hashed password matches the password given
            if content == hashed_password:
                return True

        return False

    def get_image(self, blob_name):
        """ Retrieves image data from cloud storage and converts it to base64.
        Args:
            blob_name: Name of image blob that needs to be retrieved and displayed on website.
        Returns:
            image: Image data converted to base64 for front-end use.
        """
        bucket = self.client.get_bucket('wiki-content-techx')
        blob = bucket.get_blob(blob_name)
        with blob.open('rb') as f:
            content = f.read()
        image = self.base64func.b64encode(content).decode("utf-8")
        return image

    def get_user(self, username):
        """ Creates User object containing username and hashed password retreived from cloud storage.
        Args:
            username: The username that the user inputs.
        Returns:
            User(username, password): User object for account related use.
        """
        bucket = self.client.get_bucket('users-passwords-techx')
        blob = bucket.get_blob(username)

        if blob:
            with blob.open('r') as f:
                password = f.read()
            return User(username, password)
        else:
            return None

#------------------------------------ Search Filter ------------------------------------#
    def get_pages_using_filter_and_search(self, name, type, region, nature, sorting):
        """ Retrieves all pages that match filter options selected by the user.
        Args:
            name: The name of the wiki page we are looking for.
            type: The type of the pokemon we are looking for.
            region: The region of the pokemon we are looking for.
            nature: The nature of the pokemon we are looking for.
            sorting: The sorting metric that the user selected.                         
        Returns:
            page_names: The names of all pages that match filter criteria selected by user.
        """
        bucket = self.client.get_bucket('wiki-content-techx')
        blobs = bucket.list_blobs(prefix='pages/')
        page_content = []
        page_names = []

        for index, blob in enumerate(blobs):
            if index == 0:
                continue
            with blob.open('r') as f:
                content = f.read()
            pokemon_data = self.json.loads(content)
            if (name == None or name.lower() in pokemon_data["name"].lower()) and (type == None or pokemon_data["type"] == type) and (region == None or pokemon_data["region"] == region) and (nature == None or pokemon_data["nature"] == nature):
                page_names.append(blob.name)
                if sorting:
                    level = int(pokemon_data["level"])
                    page_content.append([level, blob.name])
                                        
        if sorting:
            return self.get_pages_using_sorting(page_content, sorting)

        return page_names


    def get_pages_using_sorting(self, pages_content, sorting):
        """ This function sorts the page names that meet the filter criteria by level.
        Args:
            pages_content: List of tuples containing page names and there respective level.
            sorting: The sorting metric that the user selected.                       
        Returns:
            page_names: The names of the pages in the order determined by the sorting metric.
        """
        bucket = self.client.get_bucket('wiki-content-techx')
        
        if sorting == "LowestToHighest":
            pages_content.sort()
        if sorting == "HighestToLowest":
            pages_content.sort(reverse = True)

        page_names = []

        for level, name in pages_content:
            page_names.append(name)

        return page_names
        

    def get_pages_using_search(self, name):
        '''Gets all the pages that match the given name.
        Args:
            name: Name or part of the name of a wiki page.
        Rturns:
            page_names: The name of the pages that match the given name.
        '''
        bucket = self.client.get_bucket('wiki-content-techx')
        blobs = bucket.list_blobs(prefix='pages/')
        page_names = []

        for index, blob in enumerate(blobs):
            if index == 0:
                continue
            with blob.open('r') as f:
                content = f.read()
            content = self.json.loads(content)
            if name in content["name"].lower():
                page_names.append(blob.name)

        return page_names

#------------------------------------ Game ------------------------------------#
    def get_seen_pokemon(self, username): 
        """
        Gets a json object that stores the pokemon that the user has seen so far
        """
        game_users_bucket = self.client.get_bucket('wiki-content-techx')
        path = f'user_game_ranking/seen/{username}'
        blob = game_users_bucket.get_blob(path)
        # turn data into json
        json_str = blob.download_as_string()
        json_obj = self.json.loads(json_str)

        return json_obj
    
    def update_seen_pokemon(self,username,new_list):
        """
        takes a json object to overwrite the old blob
        """
        bucket = self.client.get_bucket("wiki-content-techx")
        seen_path = f"user_game_ranking/seen/{username}"
        blob = bucket.blob(seen_path)
        new_seen = self.json.dumps(new_list)

        # if the lenght of the json object is greater than the number of pokemon,
        # then we set the json object to an empty state
        if len(new_seen) > MAX_ID:
            new_seen = json.dumps({})
        # upload blob
        blob.upload_from_string(data=new_seen, content_type="application/json")

    def get_pokemon_image(self,id):
        """
        Gets a pokemon image using the pokemon's unique id
        """
        image_id = "{:03d}".format(id)
        bucket = self.client.get_bucket("wiki-content-techx")
        image_path = "master_pokedex/images/" + image_id + ".png"
        # Get from bucket
        pokemon_image_blob = bucket.get_blob(image_path)
        # Read contents into base64
        with pokemon_image_blob.open('rb') as f:
            content = f.read()
        pokemon_image = self.base64func.b64encode(content).decode("utf-8")
        return pokemon_image

    def get_pokeball(self):
        """
        Returns the pokeball image
        """
        bucket = self.client.get_bucket("wiki-content-techx")
        image_path = "master_pokedex/images/pokeball.png"
        pokeball_blob = bucket.get_blob(image_path)
        # Read contents into base64
        with pokeball_blob.open('rb') as f:
            content = f.read()
        pokeball_image = self.base64func.b64encode(content).decode("utf-8")
        return pokeball_image

    def get_pokemon_data(self,id):
        """
        Returns a json obj with the pokemon data for that particular id
        """
        bucket = self.client.get_bucket("wiki-content-techx")
        data_path = "master_pokedex/pokedex.json"
        pokedex_blob = bucket.get_blob(data_path)
        poke_str = pokedex_blob.download_as_string()
        pokedex_json = self.json.loads(poke_str)
        pokemon_json = pokedex_json[id-1]
        return pokemon_json

#------------------------------------ Leaderboard ------------------------------------#
    def get_categories(self):
        bucket = self.client.get_bucket("wiki-content-techx")
        blob = bucket.get_blob("filtering/categories.json")
        with blob.open() as f:
            content = f.read()
        categories = json.loads(content)
        return categories
    
    def get_game_user(self, username):
        '''Gets game data for a specific user.
        Args:
            username: Username of the current user.
        Returns:
            JSON object containing user username, points and rank.
        '''
        game_users_bucket = self.client.get_bucket('wiki-content-techx')
        path = f'user_game_ranking/game_users/{username}'

        blob = game_users_bucket.get_blob(path)
        json_str = blob.download_as_string()
        json_obj = self.json.loads(json_str)

        return json_obj
    
    def update_points(self, username, new_score):
        """Updates the game stats of the user.
        Update the current user's points and rank, leaderboard is updated as well.
        Args:
            username: Username of the current user playing.
            new_score: New amount of points gained or lost by playing the game.
        """
        user = self.get_game_user(username)
        user["points"] = new_score
        new_user = self.update_leaderboard(user)

        bucket = self.client.get_bucket("wiki-content-techx")
        path = "user_game_ranking/game_users/" + username
        blob = bucket.blob(path)
        json_data = self.json.dumps(new_user)
        # upload new data
        blob.upload_from_string(data=json_data,content_type="application/json")
    
    def get_leaderboard(self):
        '''Gets the leaderboard list containing all users that have played the game.
        Returns:
            List of JSON objects with each user's game information.
        '''
        bucket = self.client.get_bucket("wiki-content-techx")
        blob = bucket.get_blob("user_game_ranking/ranks_list.json")
        json_str = blob.download_as_string()
        json_obj = self.json.loads(json_str)
        return json_obj["ranks_list"]

    def update_leaderboard(self, updated_user):
        '''Updates the leaderboard by sorting the users by points and ranks.
        Args:
            updated_user: Current user with new points gained or lost from playing the game.
        Returns:
            Updated user with new rank assigned.
        '''
        leaderboard = self.get_leaderboard()

        # If user is not on the leaderboard
        if not updated_user["rank"]: 
            updated_user["rank"] = len(leaderboard) + 1
            leaderboard.append(updated_user)
            new_info = self.sort_leaderboard(leaderboard, updated_user, True)
            leaderboard = new_info[0]
            updated_user = new_info[1]

        # Only user in the leaderboard, update leaderboard with new points
        elif (len(leaderboard) == 1 and updated_user["name"] == leaderboard[0].get("name")):
            leaderboard[0] = updated_user

        # User is in the leaderboard
        else:
            new_info = self.sort_leaderboard(leaderboard, updated_user, False)
            leaderboard = new_info[0]
            updated_user = new_info[1]

        bucket = self.client.get_bucket("wiki-content-techx")
        blob = bucket.blob("user_game_ranking/ranks_list.json")
        json_obj = {"ranks_list": leaderboard}
        new_data = self.json.dumps(json_obj)
        
        blob.upload_from_string(data=new_data, content_type="application/json")
        
        # Updated user
        return updated_user

    def sort_leaderboard(self, leaderboard, user, is_new_user):
        '''Sorts the leaderboard by points and ranks.
        If the user lost points it would move down the user to the right position in the leaderboard if necessary.
        If the user gained points it would move up the user to the right position in the leaderboard if necessary.
        Args:
            leaderboard: Leaderboard list with all user game stats.
            user: Current user being moved up or down on rank.
        Returns:
            Tuple with the updated leaderboard and current user with updated rank.
        '''
        user_index = user["rank"] - 1
        old_user = leaderboard[user_index]
        user_points = user["points"]

        def sort_up(user_index, user_points):
            # User to compare
            other_user_index = user_index - 1
            other_user = leaderboard[other_user_index]
            other_user_points = other_user.get("points")

            # User did not rank up
            if user_points <= other_user_points or user_index == 0:
                leaderboard[user_index] = user
                return leaderboard, user

            # User ranked up        
            while other_user_index >= 0 and user_points > other_user_points:

                # Update ranks and leaderboard with new ranks
                user["rank"] = user['rank'] - 1
                other_user["rank"] = other_user["rank"] + 1 
                
                # Update other user rank to game_users bucket
                self.update_user_rank(other_user)

                leaderboard[other_user_index] = other_user
                leaderboard[user_index] = user

                # Update leaderboard list
                leaderboard[other_user_index], leaderboard[user_index] = leaderboard[user_index], leaderboard[other_user_index]

                # Updates index
                user_index -= 1
                other_user_index -= 1

                if other_user_index >= 0:
                    # Get new other user
                    other_user = leaderboard[other_user_index]
                    other_user_points = other_user["points"]
            
            return leaderboard, user
            
        def sort_down(user_index, user_points):
            
            # Checks if the current user is on the last index of the list, if not it assigns another user to be compared
            other_user_index = user_index + 1 if user_index < len(leaderboard) - 1 else None
            other_user = leaderboard[other_user_index] if other_user_index else None
            other_user_points = other_user.get("points") if other_user_index else None

            # Current user is in the last spot or did not rank down
            if other_user_index is None or user_points >= other_user_points:
                leaderboard[user_index] = user
                return leaderboard, user
            
            while (other_user_index <= len(leaderboard) - 1) and user_points <= other_user_points:
            
                # Update ranks and leaderboard with new ranks
                user["rank"] = user['rank'] + 1
                other_user["rank"] = other_user["rank"] - 1 

                # Update other user rank to game_users bucket
                self.update_user_rank(other_user)
                
                leaderboard[other_user_index] = other_user
                leaderboard[user_index] = user

                # Update leaderboard list
                leaderboard[other_user_index], leaderboard[user_index] = leaderboard[user_index], leaderboard[other_user_index]

                # Updates index
                user_index += 1
                other_user_index += 1

                if other_user_index <= len(leaderboard) - 1:
                    # Get new other user
                    other_user = leaderboard[other_user_index]
                    other_user_points = other_user["points"]
            
            return leaderboard, user

        if is_new_user:
            return sort_up(user_index, user_points)

        if old_user["points"] < user_points:
            return sort_up(user_index, user_points)
        
        return sort_down(user_index, user_points)

    def update_user_rank(self, updated_user):
        '''Updates game_users/user bucket with new rank.
        Args:
            updated_user: User with new rank assigned
        '''
        bucket = self.client.get_bucket("wiki-content-techx")
        path = "user_game_ranking/game_users/" + updated_user["name"]
        blob = bucket.blob(path)
        json_data = self.json.dumps(updated_user)

        blob.upload_from_string(data=json_data,content_type="application/json")