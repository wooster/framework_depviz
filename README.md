# Framework Depviz

A simple tool to visualize OS X and iOS framework dependencies.

This tool generates a Graphviz dot file of the framework dependencies at a given system library root.

Example usage:

`./depviz.py /System/Library > dependencies.dot`

This will create a file named `dependencies.dot` which can be opened with Graphviz.

You might also do:

`./depviz.py "~/Library/Developer/Xcode/iOS DeviceSupport/5.1.1 (9B206)/Symbols/System/Library/" AirTraffic > airtraffic.dot`

To generate a graph of just the dependencies of `AirTraffic.framework`. This graph might look like:

![AirTraffic Graph](screenshots/airtraffic.png?raw=true)


You can append multiple names, eg:

`./depviz.py "~/Library/Developer/Xcode/iOS DeviceSupport/5.1.1 (9B206)/Symbols/System/Library/" AirTraffic CoreVideo`

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

`dot -v -Gnslimit=20 -Gmaxiter=10 -Gmaxiter1=10 -Tpdf -o deps.pdf deps.dot`

Which will generate a PDF of the output called `deps.pdf`.
