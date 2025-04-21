

import marimo

__generated_with = "0.13.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    from salesfunk import Salesfunk
    return (Salesfunk,)


@app.cell
def _(Salesfunk):
    sf = Salesfunk(domain='test')
    sf.connect()
    return


if __name__ == "__main__":
    app.run()
