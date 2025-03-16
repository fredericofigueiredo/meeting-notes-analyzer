import aws_cdk as core
import aws_cdk.assertions as assertions

from meeting_notes_analyzer.meeting_notes_analyzer_stack import MeetingNotesAnalyzerStack

# example tests. To run these tests, uncomment this file along with the example
# resource in meeting_notes_analyzer/meeting_notes_analyzer_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = MeetingNotesAnalyzerStack(app, "meeting-notes-analyzer")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
