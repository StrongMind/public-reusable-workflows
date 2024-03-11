# TODO:  container.py logs


  # self.logs = aws.cloudwatch.LogGroup(
  #           log_name,
  #           retention_in_days=14,
  #           name=f'/aws/ecs/{self.project_stack}',
  #           tags=self.tags
  #       )
  #       self.log_metric_filter_definitions = kwargs.get('log_metric_filters', [])
  #       for log_metric_filter in self.log_metric_filter_definitions:
  #           self.log_metric_filters.append(
  #               aws.cloudwatch.LogMetricFilter(
  #                   log_metric_filter["metric_transformation"]["name"],
  #                   name=self.project_stack + "-" + log_metric_filter["metric_transformation"]["name"],
  #                   log_group_name=self.logs.name,
  #                   pattern=log_metric_filter["pattern"],
  #                   metric_transformation=aws.cloudwatch.LogMetricFilterMetricTransformationArgs(
  #                       name=self.project_stack + "-" + log_metric_filter["metric_transformation"]["name"],
  #                       value=log_metric_filter["metric_transformation"]["value"],
  #                       namespace=log_metric_filter["metric_transformation"]["namespace"],
  #                       unit="Count"
  #                   )
  #               )
  #           )