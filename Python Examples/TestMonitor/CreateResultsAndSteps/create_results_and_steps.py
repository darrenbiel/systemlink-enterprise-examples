"""
SystemLink Enterprise TestMonitor create results and steps example

This is an example of uploading test results to the SystemLink Test Monitor service.
It simulates measuring the power output from a device and tests the measured power
to ensure it is within a specified upper and lower limit.  The power is simulated using
a simple electrical equation P=VI (power=voltage*current).  In this example, a random
amount of current loss and voltage loss are induced to simulate a non-ideal device.

A top level result is created containing metadata about the overall test.

The example sweeps across a range of input currents and voltages and takes measurements
for each combination and stores a single measurement within each test step.  The test
steps are associated with the test result, and in some cases, as child relationships
to other test steps.  Each step is uploaded to the SystemLink Enterprise as it is generated.
At the end, the step status is evaluated to set the status of the parent step and
ultimately sets the status of the top-level test result.
"""

import random
import os
import sys
import uuid
import datetime
from typing import Any, Tuple, Dict, List

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)

import test_data_manager_client

def measure_power(current: float, voltage: float = 0) -> Tuple[float, List[Any], List[Any]]:
    """
    Simulates taking an electrical power measurement.
    This introduces some random current and voltage loss.
    :param current: The electrical current value.
    :param voltage: The electrical voltage value.
    :return: A tuple containing the electrical power measurements and the input and output lists.
    """
    current_loss = 1 - random.uniform(0, 1) * 0.25
    voltage_loss = 1 - random.uniform(0, 1) * 0.25
    power = current * current_loss * voltage * voltage_loss

    # Record electrical current and voltage as inputs.
    inputs = [{"name":"current", "value":current}, {"name":"voltage", "value":voltage}]

    # Record electrical power as an output.
    outputs = [{"name":"power", "value":power}]

    return power, inputs, outputs


def build_power_measurement_params(power: float, low_limit: float, high_limit: float, status: Any) -> Any:
    """
    Builds a Test Monitor measurement parameter object for the power test.
    :param power: The electrical power measurement.
    :param low_limit: The value of the low limit for the test.
    :param high_limit: The value of the high limit for the test.
    :param status: The measurement's pass/fail status.
    :return: A list of test measurement parameters.
    """
    parameter = {
        "name": "Power Test",
        "status": str(status["statusType"]),
        "measurement": str(power),
        "units": "Watts",
        "nominalValue": None,
        "lowLimit": str(low_limit),
        "highLimit": str(high_limit),
        "comparisonType": "GELE"
    }

    parameters = {"text": "", "parameters": [parameter]}
    return parameters


def generate_step_data(
    name: str,
    step_type: str,
    inputs: List[Any] = None,
    outputs: List[Any] = None,
    parameters: Any = None,
    status: Dict = None,
):
    """
    Creates the step data and
    populates it to match the TestStand data model.
    :param name: The test step's name.
    :param step_type: The test step's type.
    :param inputs: The test step's input values.
    :param outputs: The test step's output values.
    :param parameters: The measurement parameters.
    :param status:
    :return: The step data used to create a test step.
    """
    step_status = status if status else {
        "statusType": "RUNNING",
        "statusName": "Running"
        }

    step_data = {
        "stepId": None,
        "parentId": None,
        "resultId": None,
        "children": None,
        "data": parameters,
        "dataModel": "TestStand",
        "name": name,
        "startedAt": None,
        "status": step_status,
        "stepType": step_type,
        "totalTimeInSeconds": random.uniform(0, 1) * 10,
        "inputs": inputs,
        "outputs": outputs
    }

    return step_data


def update_step_status(step: Any, status: str) -> Any:
    """
    Updates the step status based on the given status string
    :param step: represents step which needs to be updated
    :param status: string representing the current status of the step
    :return: Update steps API response
    """
    if(status == "Passed"):
        step["status"] = {
            "statusType": "PASSED",
            "statusName": "Passed"
        }
    elif(status == "Failed"):
        step["status"] = {
            "statusType": "FAILED",
            "statusName": "Failed"
        }
    # Update the test step's status on the SystemLink enterprise.
    return test_data_manager_client.update_steps(steps=[step])


def create_parent_step(result_id):
    # Generate a parent step to represent a sweep of voltages at a given current.
    voltage_sweep_step_data = generate_step_data("Voltage Sweep", "SequenceCall")
    voltage_sweep_step_data["resultId"] = result_id
    # Create the step on the SystemLink enterprise.
    response = test_data_manager_client.create_steps(steps=[voltage_sweep_step_data])
    return response["steps"][0]


def create_child_steps(parent_step, result_id, current, low_limit, high_limit):
    for voltage in range(0, 10):
            # Simulate obtaining a power measurement.
            power, inputs, outputs = measure_power(current, voltage)

            # Test the power measurement.
            if power < low_limit or power > high_limit:
                status = {
                    "statusType": "FAILED",
                    "statusName": "Failed"
                }
            else:
                status = {
                    "statusType": "PASSED",
                    "statusName": "Passed"
                }
            test_parameters = build_power_measurement_params(power, low_limit, high_limit, status)

            # Generate a child step to represent the power output measurement.
            measure_power_output_step_data = generate_step_data(
                "Measure Power Output", "NumericLimit", inputs, outputs, test_parameters, status
            )
            # Create the step on the SystemLink enterprise.
            measure_power_output_step_data["parentId"] = parent_step["stepId"]
            measure_power_output_step_data["resultId"] = result_id
            response = test_data_manager_client.create_steps(steps=[measure_power_output_step_data])
            measure_power_output_step = response["steps"][0]

            # If a test in the sweep fails, the entire sweep failed.  Mark the parent step accordingly.
            if status["statusType"] == "FAILED":
                # Update the parent test step's status on the SystemLink enterprise.
                response = update_step_status(parent_step, "Failed")
                parent_step = response["steps"][0]
    
    # Update the step status if the status is still running.
    if parent_step["status"]["statusType"] == "RUNNING":
        response = update_step_status(parent_step, "Passed")
        parent_step = response["steps"][0]
    return parent_step


def main():    

    try:
        # Set test limits
        low_limit = 0
        high_limit = 70

        test_result = {
            "programName": "Power Test",
            "status": {
                "statusType": "RUNNING",
                "statusName": "Running"
            },
            "systemId": None,
            "hostName": None,
            "properties":None,
            "serialNumber": str(uuid.uuid4()),
            "operator": "John Smith",
            "partNumber": "NI-ABC-123-PWR1",
            "fileIds":None,
            "startedAt": str(datetime.datetime.now()),
            "totalTimeInSeconds": 0.0
        }

        response = test_data_manager_client.create_results(results=[test_result])
        test_result = response["results"][0]

        """
        Simulate a sweep across a range of electrical current and voltage.
        For each value, calculate the electrical power (P=IV).
        """
        for current in range(0, 10):
            voltage_sweep_step = create_parent_step(test_result["id"])
            voltage_sweep_step = create_child_steps(voltage_sweep_step, test_result["id"], current, low_limit, high_limit)

        # Update the top-level test result's status based on the most severe child step's status.
        response = test_data_manager_client.update_results(results=[test_result])
        test_result = response["results"][0]
        
    except Exception as e:
        print(e)
        print("The given URL or API key might be invalid or the server might be down. Please try again after verifying the server is up and the URL or API key is valid")
        print("For more information on how to generate API key, please refer to the documentation provided.")

if __name__ == "__main__":
    main()