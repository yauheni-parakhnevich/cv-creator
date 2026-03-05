"""Entry point for running the CV Creator web server."""

import uvicorn


def main():
    uvicorn.run("cv_creator.web.app:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
