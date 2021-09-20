<h1 align="center">Roid 🤖</h1>
<p align="center">A fast, stateless http slash commands framework for scale. Built by the Crunchy bot team.</p>
<br/>
<br/>

### 🚀 Installation
You can install roid in it's default configuration via:
```
pip install roid
```

You  can install with the optional speedups e.g. orjson with:
```
pip install roid[speedups]
```

### ❤️ Developer Note
Please note that this library is largely designed around what we need the framework to do
rather than strictly as a general API framework.

You may notice rather opinionated things e.g. how we work command groups. Which are
a trait of that. These things are generally subject to change with Discord but right
now we thing the standard command groups look rather poor.

This framework is not for everyone, if you need the gateway or general REST api calls
this is probably not the framework for you.
(Although if you would like to add some more of the slash commands REST api then feel free to PR.)
 
 
