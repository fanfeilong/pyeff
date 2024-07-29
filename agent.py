from pyouter.app import App
from pyouter.router import Router
from agent.comment import CommentAgent

if __name__=="__main__":
    config = {
        
    }
    
    app = App(config=config)
    
    app.option(
        '--token',
        dest='token',
        nargs='?',
        type=str,
        help='debug'
    )
    
    app.use(router=Router(
        agent=Router(
            comment=CommentAgent()
        )
    ))
    
    app.run()