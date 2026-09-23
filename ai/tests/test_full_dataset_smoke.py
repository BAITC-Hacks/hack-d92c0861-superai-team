import pytest

from ai.engine.data_loader import DataLoader
from ai.engine.recommender import DeterministicRecommender
from ai.tools.validate_full_dataset import find_dataset_directory


def test_available_full_dataset_loads_and_processes_an_employee():
    data_directory = find_dataset_directory()
    if data_directory is None:
        pytest.skip("No complete local Career Quest dataset is available.")

    loader = DataLoader.from_directory(data_directory)
    dataset = loader.load_all()
    assert dataset.employees
    assert dataset.skills
    assert dataset.role_profiles
    assert dataset.events

    employee_id = dataset.employees[0]["employee_id"]
    result = DeterministicRecommender(loader).recommend(employee_id, top_k=1)

    assert result.employee_id == employee_id
    assert len(result.candidates) <= 1
    assert all(0.0 <= candidate.score <= 1.0 for candidate in result.candidates)
