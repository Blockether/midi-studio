# MIDI Studio

A MIDI studio in Python. Each song is code: [music21](https://www.music21.org/) turns keys,
scale steps and chord symbols into notes. The studio shows the notes as a piano roll, plays
them in the browser and gives each song as a Standard MIDI File.

The studio runs in its own AWS Lambda function, with a public address. [Deploy](#deploy) tells
how to put a new version there.

## Files

- `src/studio/songs.py` has the songs and the catalog. Change a line there and the music changes.
- `src/studio/app.py` is the web app (WSGI, standard library only): the page, the songs as JSON and the MIDI files.
- `src/studio/public/` has the page: a piano roll and a player on the Web Audio API. It has no build step.
- `src/studio/aws.py` is the entry of the Lambda function. It turns a function URL event into a WSGI request.
- `tests/` has the tests. They read the MIDI file of each song of the catalog.
- `Dockerfile`, `template.yaml` and `deploy.sh` are the deployment.

## Run it

```sh
python3 -m pip install music21 pytest
PYTHONPATH=src python3 -m studio          # the page, on http://127.0.0.1:8090/
PYTHONPATH=src python3 -m studio render   # the MIDI file of each song, in out/
python3 -m pytest
```

## Add a song

1. Write a function in `src/studio/songs.py` that returns the parts of the song. `part` makes a
   part with a General MIDI program, `drums` makes the drum part and `line` puts notes one after
   the other. Time is in quarter notes.
2. Add one `Song` with a new id to `CATALOG`.
3. Run the tests: they check each song of the catalog.

## Deploy

You need the AWS CLI version 2 with credentials that can make the stack, and Docker or Podman.

```sh
./deploy.sh                  # prints the address of the studio
ENGINE=podman ./deploy.sh    # the same, with Podman
```

The script builds the image, pushes it to Amazon ECR and deploys [`template.yaml`](template.yaml).
It is safe to run again. The stack has one function with a function URL and one log group.

| Variable | Default | Use |
| --- | --- | --- |
| `STACK` | `midi-studio` | The name of the stack, of the function and of the ECR repository |
| `AWS_REGION` | `eu-central-1` | The region |
| `ENGINE` | `docker` | `docker` or `podman` |

- The address is public and needs no password. The studio only reads its own files.
- The function has no permission for an AWS service. It writes only its own log.
- At most 5 requests run at the same time. An answer has at most 30 seconds.
- A push to `main` does not deploy. GitHub Actions is off in this repository, because Vis
  sessions can push here. Run `deploy.sh` to put a version on Lambda.

To remove the deployment, delete the stack and then the ECR repository:

```sh
aws cloudformation delete-stack --stack-name midi-studio
aws ecr delete-repository --repository-name midi-studio --force
```

## Vis sessions

[Durable Lambda](https://github.com/Blockether/vis/tree/main/examples/durable-lambda) is a
separate stack that runs Vis on AWS Lambda. Its sessions and workflows get a clone of the
`main` branch of this repository. They can read, change and test the code, and publish their
commits back here. That stack does not run the studio, and this repository holds no part of it.
