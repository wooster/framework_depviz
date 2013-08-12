# Framework Depviz

A simple tool to visualize OS X and iOS framework dependencies.

This tool generates a Graphviz dot file of the framework dependencies at a given system library root.

Example usage:

`./depviz.py /System/Library > dependencies.dot`

This will create a file named `dependencies.dot` which can be opened with Graphviz.

## Installing Graphviz on OS X

The most reliable method for installing Graphviz on OS X I've found is with Homebrew:

`brew install graphviz --with-app`

then:

`brew linkapps`

If you have an old version of Graphviz, you may need to use:

`brew link --overwrite graphviz`

to overwrite the previous install.

## Using Graphviz

You may use the application, although it will hang for a long time generating graphs.

I usually find it nicer to use the command line, eg:

`dot -v -Tpdf -o deps.pdf deps.dot`

Which will generate a PDF of the output called `deps.pdf`.
