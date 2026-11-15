# The image of the studio for AWS Lambda.
FROM public.ecr.aws/lambda/python:3.13

# music21 writes its settings in the home directory. In Lambda, only /tmp is writable.
ENV HOME=/tmp MPLCONFIGDIR=/tmp

RUN pip install --no-cache-dir music21
COPY src/studio ${LAMBDA_TASK_ROOT}/studio
# The build stops when the studio cannot make a song.
RUN python -c "from studio.aws import handler; assert handler({'rawPath': '/api/songs'})['statusCode'] == 200"

CMD ["studio.aws.handler"]
