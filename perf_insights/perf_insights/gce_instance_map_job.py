# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import argparse
import json
import os
import sys
import traceback

import perf_insights
from perf_insights import corpus_driver_cmdline
from perf_insights import corpus_query
from perf_insights import map_runner
from perf_insights.mre import function_handle
from perf_insights.mre import job as job_module
from perf_insights.mre import map_results
from perf_insights.results import json_output_formatter


_DEFAULT_DESCRIPTION = """
Entry point for the cloud mapper. Please consider using
perf_insights/bin/map_traces for normal development."""


def Main(argv):
  parser = argparse.ArgumentParser(
      description=_DEFAULT_DESCRIPTION)
  corpus_driver_cmdline.AddArguments(parser)
  parser.add_argument('--map_function_handle')
  parser.add_argument('--reduce_function_handle')
  parser.add_argument('-o', '--output-file')

  args = parser.parse_args(argv[1:])
  corpus_driver = corpus_driver_cmdline.GetCorpusDriver(parser, args)
  query = corpus_query.CorpusQuery.FromString('True')

  if not args.output_file:
    parser.exit("No output file specified.")

  ofile = open(args.output_file, 'w')
  output_formatter = json_output_formatter.JSONOutputFormatter(ofile)

  try:
    job = None
    if args.map_function_handle:
      map_handle = function_handle.FunctionHandle.FromUserFriendlyString(
          args.map_function_handle)
      job = job_module.Job(map_handle, None)
    elif args.reduce_function_handle:
      reduce_handle = function_handle.FunctionHandle.FromUserFriendlyString(
          args.reduce_function_handle)
      job = job_module.Job(None, reduce_handle)
  except function_handle.UserFriendlyStringInvalidError:
    parser.error('Either mapper or reducer not specified.')

  try:
    trace_handles = corpus_driver.GetTraceHandlesMatchingQuery(query)
    runner = map_runner.MapRunner(trace_handles, job,
                                  stop_on_error=False,
                                  jobs=map_runner.AUTO_JOB_COUNT,
                                  output_formatters=[output_formatter])

    if args.map_function_handle:
      results = runner.RunMapper()
    elif args.reduce_function_handle:
      map_results_list = []
      # HACK: Maybe try to just pass in the trace handles instead
      for trace_handle in trace_handles:
        name = trace_handle._working_url.split('file://')[-1]
        with open(name, 'r') as f:
          try:
            map_dict = json.loads(f.read())
            map_results_list.append(map_results.MapResults.FromDict(map_dict))
          except ValueError:
            # TODO(simonhatch): Record this failure and pass along.
            pass

      results = runner.RunReducer([m.results for m in map_results_list])

    output_formatter.Format(results)

    return results
  finally:
    if ofile != sys.stdout:
      ofile.close()
