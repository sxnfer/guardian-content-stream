#!/usr/bin/env python3
"""Measure Lambda cold start performance.

Usage:
    python scripts/measure_cold_start.py --function-name guardian-stream-dev

This script:
1. Forces a cold start by updating the function description
2. Invokes the function and measures total duration
3. Reports cold start vs warm start times
"""

import argparse
import json
import statistics
import time

import boto3


def force_cold_start(lambda_client, function_name: str) -> None:
    """Force a cold start by updating function configuration."""
    print(f"Forcing cold start for {function_name}...")
    lambda_client.update_function_configuration(
        FunctionName=function_name,
        Description=f"Cold start test: {time.time()}",
    )
    # Wait for update to propagate
    waiter = lambda_client.get_waiter("function_updated")
    waiter.wait(FunctionName=function_name)
    print("Function updated, container will cold start on next invocation")


def invoke_and_measure(
    lambda_client, function_name: str, payload: dict
) -> tuple[float, dict]:
    """Invoke Lambda and return duration in milliseconds and response."""
    start = time.time()
    response = lambda_client.invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload),
        LogType="Tail",
    )
    duration_ms = (time.time() - start) * 1000

    # Parse response
    response_payload = json.loads(response["Payload"].read())

    return duration_ms, response_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure Lambda cold start")
    parser.add_argument(
        "--function-name",
        required=True,
        help="Lambda function name",
    )
    parser.add_argument(
        "--region",
        default="eu-west-2",
        help="AWS region (default: eu-west-2)",
    )
    parser.add_argument(
        "--warm-invocations",
        type=int,
        default=5,
        help="Number of warm invocations to measure (default: 5)",
    )
    parser.add_argument(
        "--search-term",
        default="test",
        help="Search term to use for testing (default: test)",
    )
    args = parser.parse_args()

    lambda_client = boto3.client("lambda", region_name=args.region)
    payload = {"search_term": args.search_term}

    print(f"\nMeasuring performance for: {args.function_name}")
    print(f"Region: {args.region}")
    print(f"Payload: {json.dumps(payload)}")
    print("-" * 50)

    # Cold start measurement
    force_cold_start(lambda_client, args.function_name)
    cold_start_time, cold_response = invoke_and_measure(
        lambda_client, args.function_name, payload
    )
    print(f"\nCold start: {cold_start_time:.0f}ms")
    print(f"Response: {json.dumps(cold_response)}")

    # Warm start measurements
    print(f"\nMeasuring {args.warm_invocations} warm invocations...")
    warm_times = []
    for i in range(args.warm_invocations):
        duration, response = invoke_and_measure(
            lambda_client, args.function_name, payload
        )
        warm_times.append(duration)
        status = response.get("statusCode", "?")
        print(f"  Warm invocation {i + 1}: {duration:.0f}ms (status: {status})")

    # Summary
    print("\n" + "=" * 50)
    print("PERFORMANCE SUMMARY")
    print("=" * 50)
    print(f"Cold start:       {cold_start_time:.0f}ms")
    print(f"Warm average:     {statistics.mean(warm_times):.0f}ms")
    print(f"Warm median:      {statistics.median(warm_times):.0f}ms")
    print(f"Warm min/max:     {min(warm_times):.0f}ms / {max(warm_times):.0f}ms")
    print(f"Warm std dev:     {statistics.stdev(warm_times):.0f}ms")

    # Performance assessment
    print("\n" + "-" * 50)
    if cold_start_time < 5000:
        print("Cold start is GOOD (< 5 seconds)")
    elif cold_start_time < 10000:
        print("Cold start is ACCEPTABLE (5-10 seconds)")
    else:
        print("Cold start is SLOW (> 10 seconds) - consider optimization")

    if statistics.mean(warm_times) < 1000:
        print("Warm invocations are GOOD (< 1 second average)")
    else:
        print("Warm invocations are SLOW - investigate bottleneck")


if __name__ == "__main__":
    main()
