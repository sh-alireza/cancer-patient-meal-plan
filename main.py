import json 
import logging
import os
import random 
import sys

from dotenv import dotenv_values
from fastapi import FastAPI
import openai
import requests
from random import shuffle
import tiktoken

# Create a FastAPI app
app = FastAPI()

# check for the existence of a .env file
if not os.path.exists(".env"):
    logging.error("there is no .env file, make sure that you have changed the name '.env.example' to '.env'")
    sys.exit()

# Load the OpenAI API key from the .env file
config = dotenv_values(".env")
OPENAI_API_KEY = config['OPENAI_API_KEY']

# Verify that the API key is not empty
if OPENAI_API_KEY=="":
    logging.error("the value of OPENAI_API_KEY can't be Null!!")
    sys.exit()

# Set the OpenAI API key and model name
openai.api_key = OPENAI_API_KEY
model_name = "gpt-3.5-turbo-0613"

# Database url
url = "http://data.haoma-health.com/api/v1/recipes?rpp=300"

# Send a GET request to the Database URL and check the status
resp = requests.get(url)
if resp.status_code != 200:
    logging.error(f"can't reach the Database: error {resp.status_code}")
    sys.exit()

# Iterate over each recipe in the response JSON
recipes = []
for recipe in resp.json():
    id=recipe['id']
    title=recipe['title']
    symptoms = []
    
    # Iterate over each symptom in the recipe
    for symp in recipe['symptom']:
        symptoms.append(symp['symptom']['title'])
    
    # Create a dictionary for the recipe and add it to the list
    recipes.append({
        "id":id,
        "title":title,
        "symptoms":symptoms
    })

# Shuffle the recipes list using a seed of 50
random.Random(50).shuffle(recipes)

# This is a POST request handler for the "/meal-plan" endpoint
# It takes two parameters: symptoms (string) and exception_days (string)
@app.post("/meal-plan")
def meal_plan(symptoms:str,exception_days:str):
    
    system_prompt = f"""
    you are given with a dictionary of foods with their symptoms and id in the database. suggest two food for each meal. \
    use your expert knowledge and generate a meal plan for a week of \
    this patient life. THIS IS IMPORTANT: only for {exception_days}, choose light foods, easy to digest, NOT sugary, NOT spicy, NOT cheesy, NOT processed.
    Do NOT REPEAT THE FOODS IN THE WEEK.
    the user will give you some symptoms that your meal plan MUST focus on those, try to have those symptoms in every meal.
    also check if the food is good for the meal time, for example don't put chicken with rice for breakfast.
    
    start with saturday.
    the output must be in json format with the days in keys (like saturday, sunday ...) and each day has breakfast lunch and dinner keys \
    
    for each meal time we have a list of two different dictionaries that each have keys of food_title, \
    food_id and food_symptoms.

    list of foods:{str(recipes[:44])}

    """
    
    user_prompt=symptoms
    
    # Append prompts to messages list
    messages = []
    messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    # Tokenize the system prompt using the specified model and print the count of it
    tokenizer = tiktoken.encoding_for_model(model_name)
    encoded = tokenizer.encode(system_prompt)
    print(len(encoded))

    # Generate chat response using OpenAI ChatCompletion API
    chat_response = openai.ChatCompletion.create(
        model=model_name,
        temperature=0,
        messages=messages,
    )
    
    # Extract the result from the chat response
    result = json.loads(chat_response['choices'][0]['message']['content'])
    return {"result":result}

# This is a POST endpoint that allows for changing the meal plan.
# It takes in the following parameters:
# - meal_plan: a dictionary representing the current meal plan (output of previous end-point)
# - day: a string representing the day for which the meal plan is being changed
# - meal_time: a string representing the meal time for which the meal plan is being changed
# - whole_plan: a boolean indicating whether the entire meal plan should be
@app.post("/change-meal-plan")
def variation_meal_plan(meal_plan:dict,day:str,meal_time:str,whole_plan:bool):
    
    # Handling errors of wrong inputs
    try:
        selected_meal = meal_plan[day][meal_time]
    except:
        return {"result":"wrong inputs"}
    
    # Choose new random recipes
    new_recipes = recipes
    shuffle(new_recipes)
    
    system_prompt = f"""
    the user will give you two food title that is in the list below. choose another food for the given meal_time with the same symptoms.
    the foods you are choosing must have the same symptoms as the user has given.
    DO NOT REPEAT THE SAME FOOD.
    the output must only have the given meal_time not others.
    the output must be in json format with a key of the given meal time (breakfast launch dinner), inside of that is a list of two foods with \
    the food_title, food_id and symptoms.

    list of foods:{str(new_recipes[:45])}
    """
    
    user_prompt = f"{selected_meal[0]['food_title']} for {meal_time} with symptoms: {selected_meal[0]['food_symptoms']} and \
                    {selected_meal[1]['food_title']} for {meal_time} with symptoms: {selected_meal[1]['food_symptoms']}"

    # Append prompts to messages list
    messages = []
    messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    # Tokenize the system prompt using the specified model and print the count of it
    tokenizer = tiktoken.encoding_for_model(model_name)
    encoded = tokenizer.encode(system_prompt)
    print(len(encoded))

    # Generate chat response using OpenAI ChatCompletion API
    chat_response = openai.ChatCompletion.create(
        model=model_name,
        temperature=0,
        messages=messages,
    )
    
    # Extract the result from the chat response
    result = json.loads(chat_response['choices'][0]['message']['content'])
    
    # Check if the user wants the whole meal plan as output or not
    if whole_plan:
        
        # Return the whole new meal plan
        meal_plan[day][meal_time] = result[meal_time]
        return {"result":meal_plan}
    else:
        
        # Return only the new meal time foods
        return {"result":result}
