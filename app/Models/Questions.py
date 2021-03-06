import json
import uuid
import copy
from typing import Dict, List
from abc import ABC, abstractmethod
from app.Models.Response import Response


class Question(ABC):

    def __init__(self, object_id=None, responses: List[Response] = None, type: str = None):
        self.type = type
        if object_id is None:
            self.object_id = str(uuid.uuid4())
        else:
            self.object_id = object_id
        self._responses: List[Response] = []

    @property
    @abstractmethod
    def json_data(self) -> Dict:
        return {}

    def get_type(self) -> str:
        return self.type

    @staticmethod
    def create_a_question(question_representation):
        """
        Factory method to create a Question Object dynamically at runtime.
        :param question_representation: The JSON object as a dictionary.
        :return: A Question Object representing the type of question in the json_string
        """
        question_representation = copy.deepcopy(question_representation)
        if isinstance(question_representation, Question):
            return question_representation
        if isinstance(question_representation, dict):
            json_as_dictionary = question_representation
            del question_representation
        elif isinstance(question_representation, str):
            json_as_dictionary = json.loads(question_representation)
            del question_representation
        else:
            raise TypeError("The json representation must be a dictionary")
        question_type = json_as_dictionary.get('type')
        json_as_dictionary.pop('type')
        json_as_dictionary.pop('kind')
        if question_type is None:
            raise ValueError("The value passed to create_a_question_from_json must be question and have a type")
        if question_type == 'multiple_choice':
            return MultipleChoiceQuestion(**json_as_dictionary)
        elif question_type == 'matching':
            return MatchingQuestion(**json_as_dictionary)
        elif question_type == 'short_answer':
            return ShortAnswerQuestion(**json_as_dictionary)
        elif question_type == 'fill_in_the_blank':
            return FillInTheBlankQuestion(**json_as_dictionary)
        else:
            raise ValueError("This question type is not supported: {}".format(question_type))

    def add_response(self, response: Response):
        """
        :param response:
        :return:
        """
        if not isinstance(response, Response):
            raise ValueError("Only Response objects are allowed")
        if response.get_type() != self.get_type():
            raise ValueError("Invalid response type: {} for a question of type: {}")
        self.validate_response(response)
        self._responses.append(response)

    def _initialize_responses(self, responses: List[Dict or Response]):
        if responses is not None and len(responses) > 0:
            response_objects = [Response.create_a_response(response) if isinstance(response, dict) else response for
                                response in responses]
            for response_object in response_objects:
                self.add_response(response_object)

    @abstractmethod
    def validate_response(self, response: Response):
        pass

    def get_responses(self):
        return self._responses

    def __eq__(self, other):
        if type(other) is type(self):
            return self.__dict__ == other.__dict__
        return False


class MultipleChoiceQuestion(Question):
    """
    Represents a Multiple Choice Question object.
    """

    def __init__(self, prompt: str, choices: List[str], answer: str, responses: List[Dict or Response] = None,
                 object_id=None):
        """
        :param prompt: The prompt for the multiple choice question
        :param choices: Dictionary with the answer choice keys and their prompts
        :param answer: A key in the above dictionary(i.e. a, b, c, d)
        :param responses: A list of Responses in dictionary or Response object format
        """
        super().__init__(object_id, responses, 'multiple_choice')
        self.prompt = prompt
        self.choices = list(dict.fromkeys(choices))
        self.answer = answer
        self._initialize_responses(responses)
        if self.answer not in choices:
            raise ValueError("The answer must be reflected in the choices")

    @property
    def json_data(self) -> Dict:
        return {'kind': 'question', 'object_id': self.object_id, 'type': "multiple_choice", 'prompt': self.prompt,
                'choices': self.choices,
                'answer': self.answer,
                'responses': [response.json_data for response in self._responses]}

    def validate_response(self, response: Response):
        response_json = response.json_data
        if 'choice' not in response_json:
            raise ValueError("The key choice is not in the representation of this response {}".format(response_json))
        choice = response_json['choice']
        if choice not in self.choices:
            raise ValueError("Response choice present but not reflected in question choices")


class MatchingQuestion(Question):

    def __init__(self, prompt: str, left_choices: List[str], right_choices: List[str],
                 answer: Dict[str, str], responses: List[Dict or Response] = None, object_id=None):
        """

        :param prompt: The prompt for the multiple choice question :param left_choices: The choices on the left for
        the user to match to the choices on the right. :param right_choices: The choices on the right to be matched
        by the user to the choices on the right. :param answer_mapping: A mapping consisting of keys that are answer
        choices on the left with values that are answer choices on the right. :param responses: A list of tuples
        which themselves are mappings of answer choices on the left to answer choices on the right.
        """
        super().__init__(object_id, responses, 'matching')
        self.prompt = prompt
        # Remove duplicates while preserving insertion order(By default uses OrderedDict)
        self.left_choices = list(dict.fromkeys(left_choices))
        self.right_choices = list(dict.fromkeys(right_choices))
        self.answer = answer
        if not all(left_choice in self.left_choices for left_choice in self.answer.values()):
            raise ValueError("All left choices in the question must be reflected in the answer choices")
        if not all(correct_answer in self.right_choices for correct_answer in self.answer.values()):
            raise ValueError("All of the right choices in the answer must be reflected in the question")
        self._initialize_responses(responses)

    def validate_response(self, response: Response):
        response_json = response.json_data
        if 'answer_mapping' not in response_json.keys():
            raise ValueError("There is no answer mapping present in the response {}".format(response_json))
        left = response_json['answer_mapping'].keys()
        right = response_json['answer_mapping'].values()
        assert len(right) == len(left)
        if not list(left) == self.left_choices:
            raise ValueError("Left choices for the answer must be the same as the left choices for the question")
        if not all(
                [right_choice in self.right_choices or right_choice is None for right_choice in right]):
            raise ValueError("Right_choices for this question object does not contain the key's "
                             "specified in the response")
        return

    @property
    def json_data(self) -> Dict:
        return {'kind': 'question', 'object_id': self.object_id, 'type': "matching", 'prompt': self.prompt,
                'left_choices': self.left_choices,
                'right_choices': self.right_choices, 'answer': self.answer,
                'responses': [response.json_data for response in self._responses]}


class ShortAnswerQuestion(Question):
    """
    A question where a user is given a prompt and is allowed to answer with text input.
    """

    def __init__(self, prompt: str, answer: str, responses: List[Dict or Response] = None, object_id=None):
        """
        :param prompt: The prompt for the question
        :param answer: The answer to the question.
        :param responses: A list of responses received on this object to the question in dictionary or Response object format
        """
        super().__init__(object_id, responses, 'short_answer')
        self.prompt = prompt
        self.answer = answer
        self._initialize_responses(responses)

    def validate_response(self, response: Response):
        response_json = response.json_data
        return

    @property
    def json_data(self) -> Dict:
        return {'kind': 'question', 'object_id': self.object_id, 'type': 'short_answer', 'prompt': self.prompt,
                'answer': self.answer, 'responses': [response.json_data for response in self._responses]}


class FillInTheBlankQuestion(Question):
    """
    A question where a user is given a blank in a prompt and is required to fill it out
    """

    def __init__(self, before_prompt: str, after_prompt: str, answer: str, responses: List[Dict or Response] = None,
                 object_id=None):
        """

        :param before_prompt: The text before the blank
        :param after_prompt: The text after the blank
        :param correct_answer: The correct answer to the question
        :param responses: A list of responses to the question in dictionary or response format.
        """
        super().__init__(object_id, responses, 'fill_in_the_blank')
        self.before_prompt = before_prompt
        self.after_prompt = after_prompt
        self.answer = answer
        self._initialize_responses(responses)

    def validate_response(self, response: Response):
        response_json = response.json_data
        return

    @property
    def json_data(self) -> Dict:
        return {'kind': 'question', 'object_id': self.object_id, 'type': 'fill_in_the_blank', 'before_prompt': self.before_prompt,
                'after_prompt': self.after_prompt, 'answer': self.answer,
                'responses': [response.json_data for response in self._responses]}

# Essentially all questions ever generated should be unique. This should come from a resource that is context aware.
# This should be decoupled from the storage(or not needed by the storage). Quiz id's should be unique as well. This
# logic will need to thought out a little more. I can see issues with deleting quizzes but still needing to keep them
# alive when there's a reference to it in client Code. Essentially, this could become an issue on the client side?
