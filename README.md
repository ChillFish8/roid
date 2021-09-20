<h1 align="center">Roid 🤖</h1>
<p align="center">A fast, stateless http slash commands framework for scale. Built by the Crunchy bot team.</p>
<br/>
<br/>

## 🚀 Installation
You can install roid in it's default configuration via:
```
pip install roid
```

You  can install with the optional speedups e.g. orjson with:
```
pip install roid[speedups]
```

## 📚 Getting Started
You can get started with the following options, most of the public API is type hinted
and a lot of the framework depends around this so you should be able to stand on your
own two feet reasonable quickly.

- **[Examples](https://github.com/ChillFish8/roid/tree/master/roid)** are the best / only place to start.

## ✨ Basic Example
```py
import os
import uvicorn

import roid

application_id = os.getenv("APPLICATION_ID")
public_key = os.getenv("PUBLIC_KEY")
token = os.getenv("BOT_TOKEN")

app = roid.SlashCommands(application_id, public_key, token)

# We can create async commands
@app.command("echo", "Echo a message.", guild_id=675647130647658527)
async def echo(message: str):
    return Response(content=message, flags=ResponseFlags.EPHEMERAL)


# Or sync commands which are ran in another thread.
# While this is not advised for everything, we do provide threadsafe interfaces
# to the state management system.
@app.command("echo-sync", "Echo a message with threading.", guild_id=675647130647658527)
def echo_sync(message: str):
    return Response(content=message, flags=ResponseFlags.EPHEMERAL)


if __name__ == "__main__":
    app.register_commands_on_start()
    uvicorn.run("app:app", port=8000)

```

## ❤️ Developer Note
Please note that this library is largely designed around what we need the framework to do
rather than strictly as a general API framework.

You may notice rather opinionated things e.g. how we work command groups. Which are
a trait of that. These things are generally subject to change with Discord but right
now we thing the standard command groups look rather poor.

This framework is not for everyone, if you need the gateway or general REST api calls
this is probably not the framework for you.
(Although if you would like to add some more of the slash commands REST api then feel free to PR.)
 
This is also why there generally arent any forms of online docs for this, i'll get
around to it, eventually.


