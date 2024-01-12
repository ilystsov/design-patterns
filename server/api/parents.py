from __future__ import annotations
import json
import os
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod

import yaml
from fastapi import APIRouter
from server import contracts


router = APIRouter()


class AbstractFileFactory(ABC):
    @abstractmethod
    def is_correct_format(self, file_path: str) -> bool:
        pass  # pragma: no cover

    @abstractmethod
    def create_parser(self) -> FileParser:
        pass  # pragma: no cover


class JSONFileFactory(AbstractFileFactory):
    def is_correct_format(self, file_path: str) -> bool:
        if file_path.endswith('.json'):
            return True
        return False

    def create_parser(self) -> JSONFileParser:
        return JSONFileParser()


class XMLFileFactory(AbstractFileFactory):
    def is_correct_format(self, file_path: str) -> bool:
        if file_path.endswith('.xml'):
            return True
        return False

    def create_parser(self) -> XMLFileParser:
        return XMLFileParser()


class YMLFileFactory(AbstractFileFactory):
    def is_correct_format(self, file_path: str) -> bool:
        if file_path.endswith(('.yaml', '.yml')):
            return True
        return False

    def create_parser(self) -> YMLFileParser:
        return YMLFileParser()


class FileParser(ABC):
    @abstractmethod
    def parse(self, file_path: str) -> dict | None:
        pass  # pragma: no cover


class JSONFileParser(FileParser):
    def parse(self, file_path: str) -> dict | None:
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return json.load(file)
        except json.JSONDecodeError:
            return None


class XMLFileParser(FileParser):
    def parse(self, file_path: str) -> dict | None:
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            persons = self._parse_parents_children(root)
            return {'persons': persons}
        except ET.ParseError:
            return None

    def _parse_parents_children(self, element) -> list[dict]:
        persons = []
        for person in element.findall('person'):
            person_dict = {'name': person.attrib['name'], 'children': []}
            for child in person.findall('child'):
                person_dict['children'].append({'name': child.attrib['name']})
            persons.append(person_dict)
        return persons


class YMLFileParser(FileParser):
    def parse(self, file_path: str) -> dict | None:
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return yaml.safe_load(file)
        except yaml.YAMLError:
            return None


class FileIterator:
    def __init__(
        self, root_directory: str, factories: list[AbstractFileFactory]
    ) -> None:
        self.root_directory = root_directory
        self.factories = factories
        self.file_generator = self._file_generator(root_directory)

    def _file_generator(self, root_directory: str):
        for dirpath, _, filenames in os.walk(root_directory):
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                yield file_path

    def __iter__(self) -> FileIterator:
        return self

    def __next__(self) -> dict | None:
        current_file_path = next(self.file_generator, None)
        if current_file_path is None:
            raise StopIteration

        for factory in self.factories:
            if factory.is_correct_format(current_file_path):
                file_parser = factory.create_parser()
                parsed_data = file_parser.parse(current_file_path)
                if parsed_data is not None:
                    return parsed_data
        return None


@router.get("/parents/{child_name}", response_model=contracts.SearchResult)
async def find_parent(child_name: str) -> contracts.SearchResult:
    parents = []
    file_iterator = FileIterator(
        './files', [JSONFileFactory(), YMLFileFactory(), XMLFileFactory()]
    )
    for file_data in file_iterator:
        for person in file_data.get('persons', []):
            if any(
                child['name'] == child_name
                for child in person.get('children', [])
            ):
                parents.append(person['name'])
    return contracts.SearchResult(found_parents=parents)
