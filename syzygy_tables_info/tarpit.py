import chess
import collections
import random
import queue
from typing import Optional

# Based on https://github.com/JamesBrill/Markov-Chain-Text-Generator/blob/master/textgen.py

class MarkovChain:
    def __init__(self, tokens: list[str], order: int) -> None:
        assert order <= len(tokens)
        self.markov_chain: collections.defaultdict[str, collections.defaultdict[str, int]] = collections.defaultdict(lambda: collections.defaultdict(int))
        current_state_queue: queue.Queue[str] = queue.Queue()
        current_state = ""
        for index, token in enumerate(tokens):
            if index < order:
                current_state_queue.put(token)
                if index == order - 1:
                    current_state = ' '.join(list(current_state_queue.queue))
            elif index < len(tokens):
                current_state_queue.get()
                current_state_queue.put(token)
                next_state = ' '.join(list(current_state_queue.queue))
                self.markov_chain[current_state][next_state] += 1
                current_state = next_state

    def get_random_state(self, rng: random.Random) -> str:
        uppercase_states = [state for state in self.markov_chain.keys() if state[0].isupper()]
        if len(uppercase_states) == 0:
            return rng.choice(list(self.markov_chain.keys()))
        return rng.choice(uppercase_states)

    def get_next_state(self, state: str, rng: random.Random) -> Optional[str]:
        next_state_items = list(self.markov_chain[state].items())
        next_states = [x[0] for x in next_state_items]
        next_state_counts = [x[1] for x in next_state_items]
        total_count = sum(next_state_counts)
        next_state_probabilities = []
        probability_total: float = 0
        for next_state_count in next_state_counts:
            probability = float(next_state_count) / total_count
            probability_total += probability
            next_state_probabilities.append(probability_total)
        sample = rng.random()
        for index, next_state_probability in enumerate(next_state_probabilities):
            if sample <= next_state_probability:
                return next_states[index]
        return None

    def generate_link(self, rng: random.Random) -> Optional[str]:
        board = chess.Board.empty()
        for _ in range(rng.randint(0, 2) or rng.randint(9, 15)): # Use cheap piece count
            board.set_piece_at(rng.choice(chess.SQUARES), chess.Piece(rng.choice(range(1, 6)), rng.choice(chess.COLORS)))
        for _ in range(20):
            bk = rng.choice(chess.SQUARES)
            wk = rng.choice(chess.SQUARES)
            board.set_piece_at(bk, chess.Piece(chess.KING, chess.BLACK))
            board.set_piece_at(wk, chess.Piece(chess.KING, chess.WHITE))
            if board.is_valid():
                break
            board.remove_piece_at(wk)
            board.remove_piece_at(bk)
        return f"/?fen={board.fen().replace(' ', '_')}"

    def generate_text(self, words: int, rng: random.Random) -> str:
        state = self.get_random_state(rng)
        text = state.split()[:words]
        while len(text) < words:
            state = self.get_next_state(state, rng) or self.get_random_state(rng)
            word = state.split()[-1]
            if len(word) > 5 and rng.randint(0, 100) < 60:
                text.append(f"<a href=\"{self.generate_link(rng)}\">{word}</a>")
            elif rng.randint(0, 100) < 5:
                text.append(f"<strong>{word}</strong>")
            elif rng.randint(0, 100) < 5:
                text.append(f"<em>{word}</em>")
            else:
                text.append(word)
        text.append(f"<a href=\"{self.generate_link(rng)}\">...</a><br><br>")
        return ' '.join(text)


TRAINING_DATA = """
Chess is a board game for two players, played on a square board consisting of 64 squares arranged in an 8×8 grid. The players, referred to as "White" and "Black", each control sixteen pieces: one king, one queen, two rooks, two bishops, two knights, and eight pawns, with each piece type having a different pattern of movement. An enemy piece may be captured (removed from the board) by moving one's own piece onto the square it occupies. The object of the game is to "checkmate" (threaten with inescapable capture) the enemy king. There are also several ways a game can end in a draw.

The recorded history of chess dates back to the emergence of chaturanga in 7th-century India. Chaturanga is also thought to be an ancestor of similar games like janggi, xiangqi, and shogi. After its introduction to Persia, it spread to the Arab world and then to Europe. The modern rules of chess emerged in Europe at the end of the 15th century, becoming standardized and gaining universal acceptance by the end of the 19th century. Today, chess is one of the world's most popular games, with millions of players worldwide.

Organized chess arose in the 19th century. International chess competitions today are governed by the International Chess Federation FIDE (Fédération Internationale des Échecs). The first universally recognized World Chess Champion, Wilhelm Steinitz, claimed his title in 1886; Gukesh Dommaraju is the current World Champion, having won the title in 2024.

A large body of chess theory has developed since the game's inception. Aspects of art are found in chess composition, and chess has in turn influenced Western culture and the arts, and has relevance to other fields such as mathematics, computer science, and psychology. One of the goals of early computer scientists was to create a chess-playing machine. In 1997, Deep Blue became the first computer to win a match with a reigning World Champion when it defeated Garry Kasparov. The chess engines of today are significantly stronger than the best human players and have greatly influenced the development of chess theory. Chess, however, is not a solved game.

White moves first, after which players alternate turns. One piece is moved per turn (except when castling, during which two pieces are moved). In the diagrams, dots mark the squares to which each type of piece can move if unoccupied by friendly pieces and there are no intervening piece(s) of either color (except the knight, which leaps over any intervening pieces). With the sole exception of en passant, a piece captures an enemy piece by moving to the square it occupies, removing it from play and taking its place. The pawn is the only piece that does not capture the way it moves, and it is the only piece that moves and captures in only one direction (forwards from the player's perspective). A piece is said to control empty squares on which it could capture, attack squares with enemy pieces it could capture, and defend squares with pieces of the same color on which it could recapture. Moving is compulsory; a player may not skip a turn, even when having to move is detrimental.

Draw by agreement: In tournament chess, draws are most commonly reached by mutual agreement between the players. The correct procedure is to make a move, to verbally offer the draw, and then to start the opponent's clock. If a draw is offered before making a move, the opponent has the right to ask the player to make a move before making their decision on whether or not to accept the draw offer. Traditionally, players were allowed to agree to a draw at any point in the game, occasionally even without having played a single move. Since the 2000s, efforts have been made to discourage early draws, for example by forbidding draw offers before a certain number of moves have been completed or even forbidding draw offers altogether.

Threefold repetition: This most commonly occurs when neither side is able to avoid repeating moves without incurring a disadvantage. The three occurrences of the position need not occur on consecutive moves for a claim to be valid. The addition of the fivefold repetition rule in 2014 requires the arbiter to intervene immediately and declare the game a draw after five occurrences of the same position, consecutive or otherwise, without requiring a claim by either player. FIDE rules make no mention of perpetual check; this is merely a specific type of draw by threefold repetition.

In competition, chess games are played with a time control. Time controls are generally divided into categories based on the amount of time given to each player, which range from classical time controls, which allot about 2 hours or more to each player and which can take upwards of seven hours (even longer if adjournments are permitted), to bullet chess, in which players receive less than three minutes each. Between these are rapid chess (ten to sixty minutes per player) and blitz chess (three to ten minutes). Non-classical chess is sometimes referred to as fast chess.

Until about 1980, the majority of English language chess publications used descriptive notation, in which files are identified by the initial letter of the piece that occupies the first rank at the beginning of the game. In descriptive notation, the common opening move 1.e4 is rendered as "1.P-K4" ("pawn to king four"). Another system, ICCF numeric notation, is recognized by the International Correspondence Chess Federation.

Chess strategy is concerned with the evaluation of chess positions and with setting up goals and long-term plans for future play. During the evaluation, players must take into account numerous factors such as the value of the pieces on the board, control of the center and centralization, the pawn structure, king safety, and the control of key squares or groups of squares (for example, diagonals, open files, and dark or light squares).

In chess, tactics generally refer to short-term maneuvers—so short-term that they can be calculated in advance by a human player. The possible depth of calculation depends on the player's ability. In quiet positions with many possibilities on both sides, a deep calculation is more difficult and may not be practical, while in positions with a limited number of forced variations, strong players can calculate long sequences of moves.

In chess, the endgame tablebase, or simply the tablebase, is a computerised database containing precalculated evaluations of endgame positions. Tablebases are used to analyse finished games, as well as by chess engines to evaluate positions during play. Tablebases are typically exhaustive, covering every legal arrangement of a specific selection of pieces on the board, with both White and Black to move. For each position, the tablebase records the ultimate result of the game (i.e. a win for White, a win for Black, or a draw) and the number of moves required to achieve that result, both assuming perfect play. Because every legal move in a covered position results in another covered position, the tablebase acts as an oracle that always provides the optimal move.

Tablebases have profoundly advanced the chess community's understanding of endgame theory. Some positions which humans had analysed as draws were proven to be winnable; in some cases, tablebase analysis found a mate in more than five hundred moves, far beyond the ability of humans, and beyond the capability of a computer during play. This caused the fifty-move rule to be called into question, since many positions were discovered that were winning for one side but drawn during play because of this rule. Initially, some exceptions to the fifty-move rule were introduced, but when more extreme cases were later discovered, these exceptions were removed. Tablebases also facilitate the composition of endgame studies.

Computer chess is one of the oldest domains of artificial intelligence, having begun in the early 1930s. Claude Shannon proposed formal criteria for evaluating chess moves in 1949. In 1951, Alan Turing designed a primitive chess-playing program, which assigned values for material and mobility; the program "played" chess based on Turing's manual calculations.[9] However, even as competent chess programs began to develop, they exhibited a glaring weakness in playing the endgame. Programmers added specific heuristics for the endgame – for example, the king should move to the center of the board. However, a more comprehensive solution was needed.

For each position, the tablebase evaluates the situation separately for White-to-move and Black-to-move. Assuming that White has the queen, almost all the positions are White wins, with checkmate forced in no more than ten moves. Some positions are draws because of stalemate or the unavoidable loss of the queen.

"The idea is that a database is made with all possible positions with a given material [note: as in the preceding section]. Then a subdatabase is made of all positions where Black is mated. Then one where White can give mate. Then one where Black cannot stop White giving mate next move. Then one where White can always reach a position where Black cannot stop [them] from giving mate next move. And so on, always a ply further away from mate until all positions that are thus connected to mate have been found. Then all of these positions are linked back to mate by the shortest path through the database. That means that, apart from 'equi-optimal' moves, all the moves in such a path are perfect: White's move always leads to the quickest mate, Black's move always leads to the slowest mate."

Each position is evaluated as a win or loss in a certain number of moves. At the end of the retrograde analysis, positions which are not designated as wins or losses are necessarily draws.

According to the method described above, the tablebase must allow the possibility that a given piece might occupy any of the 64 squares. In some positions, it is possible to restrict the search space without affecting the result. This saves computational resources and enables searches which would otherwise be impossible.

Bleicher has designed a commercial program called "Freezer", which allows users to build new tablebases from existing Nalimov tablebases with a priori information. The program could produce a tablebase for positions with seven or more pieces with blocked pawns, even before tablebases for seven pieces became available.

Syzygy tablebases were developed by Ronald de Man and released in April 2013 in a form optimized for use by a chess program during search. This variety consists of two tables per endgame: a smaller WDL (win/draw/loss) table which contains knowledge of the 50-move rule, and a larger DTZ table (distance to zero ply, i.e., pawn move or capture). The WDL tables were designed to be small enough to fit on a solid-state drive for quick access during search, whereas the DTZ form is for use at the root position to choose the game-theoretically quickest distance to resetting the 50-move rule while retaining a winning position, instead of performing a search. Syzygy tablebases are available for all 6-piece endings, and are now supported by many top engines, including Stockfish, Leela, Dragon, and Torch.

Mark Dvoretsky, an International Master, chess trainer, and author, took a more permissive stance. He was commenting in 2006 on a study by Harold van der Heijden, published in 2001, which reached the position at right after three introductory moves. The drawing move for White is 4. Kb4!! (and not 4. Kb5), based on a mutual zugzwang that may occur three moves later.

Originally, an endgame tablebase was called an "endgame data base" or "endgame database". This name appeared in both EG and the ICCA Journal starting in the 1970s, and is sometimes used today. According to Haworth, the ICCA Journal first used the word "tablebase" in connection with chess endgames in 1995.[79] According to that source, a tablebase contains a complete set of information, but a database might lack some information.

An EGTB is a set of endgames. Each endgame is a set of records about positions’ information. All involved positions in an endgame must have the same material. Typically each position's record is associated with an integer number which informs how far that position is from mating/being mated or converting (depends on the type of its metrics).

Based on values of those integer numbers it can answer directly two questions of the EGTB: 1) for a given position it is a draw or a win/loss position and 2) how far it is from mating/being mated or converting. To answer the 3rd question, the best move of a position can be indirectly calculated: generate all legal moves, make them, probe all new positions, compare probing scores for the highest one and the associated move is the best one.

Theoretically, we can add more information to each position’s record. However, due to the large number of involved positions, any additional information may make the whole EGTB become significantly larger. Thus so far none of the popular EGTBs store any extra information and their records actually contain those integers only.

All records of an endgame are simply organized as two arrays (one array for one side/colour). In other words, each item in those arrays is an integer and its index on an array is mapped to a unique position. For a given chess position, we will calculate its index and then access its data record/integer via that index without searching.

The size of an endgame depends on:

    The number of involving pieces: more pieces, the bigger size
    Type of pieces: for standard chess, more Pawns is the smaller size
    Type of metric
    The largest value: the integer number should be large enough to cover the largest value. Different endgames will have different largest values. Thus some endgames need only one byte per item but some need 2 bytes
    Indexing: The algorithms to map between an array item and a position
    Compress ratio

So far the size of an EGTB is the most important factor of success.

To summarize the different metrics of tablebases, each metric has its strengths and weaknesses. Nalimov's DTM EGTs are widely and commercially available, and used by many chess engines or chess GUIs. DTC EGTs are more easily computed and stored as they involve smaller depth ranges and are more compressible. For endgames with less or equal to 5 pieces on the board, KNNKP comes closest to requiring more than one Byte per position to store DTM: maxDTM = 115 (1-0) and 73 (0-1) necessitating 190 values in the EGT. For KPPKP, maxDTM = 127 (1-0) but only 42 (0-1). But for certain 6-piece endgames, one Byte is not enough: maxDTM = 262 for a KRNKNN position. The DTC and DTZ metrics increasingly postpone the need for two Bytes per position in an uncompressed EGT, but KRBNKQN has maxDTC = maxDTZ = 517 (0-1), both wtm and btm.

In extremis, the unmoderated use of DTM, DTC or DTZ EGTs will let slip a winnable position in the context of the 50-move rule ... hence the marginal need for the DTR and DTZR metrics, coupled with the ability to recompute DTR/DTZR EGTs in the context of a limited move-budget.

Every position is assigned to a unique index to specify the location of the information stored about it. The main purpose of indexing is to locate and read the information (from databases) such as distance to mate for a given position based on its index.

There are two main aims when generating the index number. The easier the algorithm to generate the index from any given position, the faster will be the probing of the tablebase as well as the generation of it. But the second aim is to get a relatively small range of index numbers, to keep the size of the file as small as possible.

The most straightforward way would be to for every piece on the board use 6 bit (1-64 squares).

After probing the chess engine may have the result as an integer number for the queried position. Depending on the metric, the number may be a distance to mate or distance to conversion, the position is a draw or a win or loss for the querying side. Sometimes that value (state of draw/win/loss) may be enough for searching. However, sometimes that state is not enough and it needs to know which is the best move to make. The solution is to generate all legal moves from that position, make them one by one, and probe that EGTB for the values of each new position. After all, compare the values of all children's positions to find which one is the best to make.

Typically the probe process requires some computing and it may access storage and decompress which is usually so slow. An engine that probes EGTB when searching may make the whole search be slower. Sometimes the benefit from probing EGTBs may not be enough to cover the loss of slower search. That’s why the probing should be planned and implemented carefully. EGTB files may have to be stored in fast storage and/or using some huge systems’ caches. The good point is that the engine can stop searching on the branch probed by the EGTB.

Scorpio and (iirc) Shredder are bitbases: they store whether a position is won for the side to move or not. Typically that is enough during the search, as long as the root position is not a tablebase position. In that case you need a way to make progress, and the bitbases don't really help. However, in practice chess programs can win many endgames without tablebases.
Nalimov and Gaviota store distance to mate (DTM) for the side to move (or not-won if the position is not won), but they ignore draws by the 50-move rule. Nalimov has 6 men, but comes with an obnoxious custom license. Gaviota probing code is open source under a liberal license, but it only has up to 5 men. Compression is (iirc) much better than Nalimov.
Lomonosov is DTM up to 7 pieces, but not available for free (and impractically large).
Syzygy bases store the number of moves needed to win a position under the 50-move rule (DTZ50). You win by either mating the opponent, making a winning pawn push or by converting to another won ending. The generator and probing code are open source.
For practical purposes, if you pick just one, Syzygy is probably the best pick. In a pinch, Syzygy+Gaviota might be better, since they will give you the shortest DTM in positions that are won under the 50-move rule. Syzygy alone doesn't do that. If that is better or not is a matter of taste.
Nalimov should be a no-go because of the license and Lomonosov is simply not an option.
Pure bitbases are probably the least useful these days (Syzygy and I think Gaviota actually already include bitbases for the search).

The term match may be used in multiple ways. Most commonly, it is used to refer to a tournament-match (or series, fixture, or tie), the results of which are used in some way to determine the winner of a tournament. It can also refer to a game-match (or game, rubber, or leg), one or more of which are used to determine the result of a single tournament-match. If necessary, one or more tiebreak-matches may also take place. Sometimes there are further layers, such as in tennis, where a tie (or match) can consist (but not always) of sets which themselves consist of games. For example, in the Major League Baseball postseason, a series between two teams involves up to five or seven games between the two teams, with the team that reaches three ("best of five") or four ("best of seven") wins winning the series. In the Davis Cup tennis tournament, a tie between two nations involves five rubbers between the nations' players. The team that wins the most rubbers wins the tie. In the later rounds of UEFA Champions League, each fixture is played over two legs. The scores of each leg are added, and the team with the higher aggregate score wins the fixture, with extra time, and if necessary, a penalty shoot-out used if the scores are level after both matches conclude. In this case, the first tiebreak-match is extra time (modified game-match with reduced duration) and the second tiebreak-match is a penalty shoot-out.

A multi-stage pool system was implemented by Curling Canada for the Canadian championship curling tournaments (the Scotties Tournament of Hearts for women and the Montana's Brier for men) starting in 2018. The change was intended to allow the expansion of the main stage of the tournament from twelve to sixteen teams while keeping the round robin at eleven games. The teams are seeded using a ranking system in which points are calculated based on the teams' results in all competitive bonspiels using a complicated formula. Seeds 1, 4, 5, 8, 9, 12, 13 and 16 and placed in Pool A while seeds 2, 3, 6, 7, 10, 11, 14 and 15 are placed in Pool B. After each team has played seven games, the top four teams from each pool advance to the "Championship Pool". Carrying over their entire round robin records with them, Championship Pool teams play one game against each of the four teams in the opposite pool, with the top four teams qualifying for the page playoffs. In contrast, teams that fail to qualify for the Championship Pool play only one additional "Placement Round" game against the team that finished in the same position in the opposite pool for the purposes of determining final tournament ranking. For these teams, there is little else to play for since there is no form of relegation (and, with the expansion of the field to sixteen teams, no "pre-qualifying tournament") and seeding is based solely on the performances of the participating teams and not the past results of the provinces and territories they represent.

The top Slovenian basketball league has a unique system. In its first phase, 12 of the league's 13 clubs compete in a full home-and-away season, with the country's representative in the Euroleague (an elite pan-European club competition) exempt. The league then splits. The top seven teams are joined by the Euroleague representative for a second home-and-away season, with no results carrying over from the first phase. These eight teams compete for four spots in a final playoff. The bottom five teams play their own home-and-away league, but their previous results do carry over. These teams are competing to avoid relegation, with the bottom team automatically relegated and the second-from-bottom team forced to play a mini-league with the second- and third-place teams from the second level for a place in the top league.

This board game was a race game that consisted of a board with 37 numbered pictures, each correlating to a British colony, arranged in four circular levels, numbered 1 (Heligoland, Germany) to 37 (London, England), three concentric ones and an inner fourth level of London ("Metropolis of the British Empire"). A teetotum was spun with a player's piece correspondingly moving ahead through the spaces of the game board, upon which a corresponding description to the space the player lands was read out aloud from an accompanying rule booklet by the presiding player (a player abstaining from directly playing the game), except when directed in the book. The descriptions included commentary about the various colonies and occasional game board movement directions to the player. There winner would be the player to reach London first.

Many games require some level of both skill and luck. A player may be hampered by bad luck in backgammon, Monopoly, or Risk; but over many games, a skilled player will win more often.[79] The elements of luck can also make for more excitement at times, and allow for more diverse and multifaceted strategies, as concepts such as expected value and risk management must be considered.

There are also virtual tabletop programs that allow online players to play a variety of existing and new board games through tools needed to manipulate the game board but do not necessarily enforce the game's rules, leaving this up to the players. There are generalized programs such as Vassal, Tabletop Simulator and Tabletopia that can be used to play any board or card game, while programs like Roll20 and Fantasy Grounds are more specialized for role-playing games.

With crime you deal with every basic human emotion and also have enough elements to combine action with melodrama. The player's imagination is fired as they plan to rob the train. Because of the gamble, they take in the early stage of the game there is a build-up of tension, which is immediately released once the train is robbed. Release of tension is therapeutic and useful in our society because most jobs are boring and repetitive.

The World Chess Championship is played to determine the world champion in chess. The current world champion is Gukesh Dommaraju, who defeated the previous champion Ding Liren in the 2024 World Chess Championship.

The first event recognized as a world championship was the 1886 match between Wilhelm Steinitz and Johannes Zukertort. Steinitz won, making him the first world champion. From 1886 to 1946, the champion set the terms, requiring any challenger to raise a sizable stake and defeat the champion in a match in order to become the new world champion. Following the death of reigning world champion Alexander Alekhine in 1946, the International Chess Federation (FIDE) took over administration of the World Championship, beginning with the 1948 tournament. From 1948 to 1993, FIDE organized a set of tournaments and matches to choose a new challenger for the world championship match, which was held every three years.

Before the 1993 match, then reigning champion Garry Kasparov and his championship rival Nigel Short broke away from FIDE, and conducted the match under the umbrella of the newly formed Professional Chess Association. FIDE conducted its own tournament, which was won by Anatoly Karpov, and led to a rival claimant to the title of World Champion for the next thirteen years until 2006. The titles were unified at the World Chess Championship 2006, and all the subsequent tournaments and matches have once again been administered by FIDE. Since 2014, the championship has settled on a two-year cycle, with championship matches conducted every even year.

Emanuel Lasker was the longest serving World Champion, having held the title for 27 years, and holds the record for the most Championship wins with six along with Kasparov and Karpov.

Though the world championship is open to all players, there are separate championships for women, under-20s and lower age groups, and seniors. There are also chess world championships in rapid, blitz, correspondence, problem solving, Fischer random chess, and computer chess.

The game of chess in its modern form emerged in Spain in the 15th century, though rule variations persisted until the late 19th century. Before Wilhelm Steinitz and Johannes Zukertort in the late 19th century, no chess player seriously claimed to be champion of the world. The phrase was used by some chess writers to describe other players of their day, and the status of being the best at the time has sometimes been awarded in retrospect, going back to the early 17th-century Italian player Gioachino Greco (the first player where complete games survive).

An important milestone was the London 1851 chess tournament, which was the first international chess tournament, organized by Staunton. It was played as a series of matches, and was won convincingly by the German Adolf Anderssen, including a 4–1 semi-final win over Staunton. This established Anderssen as the world's leading player.

Lasker's negotiations for title matches from 1911 onwards were extremely controversial. In 1911, he received a challenge for a world title match against José Raúl Capablanca and, in addition to making severe financial demands, proposed some novel conditions: the match should be considered drawn if neither player finished with a two-game lead; and it should have a maximum of 30 games, but finish if either player won six games and had a two-game lead (previous matches had been won by the first to win a certain number of games, usually 10; in theory, such a match might go on for ever). Capablanca objected to the two-game lead clause; Lasker took offence at the terms in which Capablanca criticized the two-game lead condition and broke off negotiations.

Up to and including the 1894 Steinitz–Lasker match, both players, with their backers, generally contributed equally to the purse, following the custom of important matches in the 19th century before there was a generally recognized world champion. For example: the stakes were £100 a side in both the second Staunton vs Saint-Amant match (Paris, 1843) and the Anderssen vs Steinitz match (London, 1866); Steinitz and Zukertort played their 1886 match for £400 a side.[60] Lasker introduced the practice of demanding that the challenger should provide the whole of the purse,[citation needed] and his successors followed his example up to World War II. This requirement made arranging world championship matches more difficult, for example: Marshall challenged Lasker in 1904 but could not raise the money until 1907.

Computer chess includes both hardware (dedicated computers) and software capable of playing chess. Computer chess provides opportunities for players to practice even in the absence of human opponents, and also provides opportunities for analysis, entertainment and training. Computer chess applications that play at the level of a chess grandmaster or higher are available on hardware from supercomputers to smart phones. Standalone chess-playing machines are also available. Stockfish, Leela Chess Zero, GNU Chess, Fruit, and other free open source applications are available for various platforms.

Computer chess applications, whether implemented in hardware or software, use different strategies than humans to choose their moves: they use heuristic methods to build, search and evaluate trees representing sequences of moves from the current position and attempt to execute the best such sequence during play. Such trees are typically quite large, thousands to millions of nodes. The computational speed of modern computers, capable of processing tens of thousands to hundreds of thousands of nodes or more per second, along with extension and reduction heuristics that narrow the tree to mostly relevant nodes, make such an approach effective.

Perhaps the most common type of chess software are programs that simply play chess. A human player makes a move on the board, the AI calculates and plays a subsequent move, and the human and AI alternate turns until the game ends. The chess engine, which calculates the moves, and the graphical user interface (GUI) are sometimes separate programs. Different engines can be connected to the GUI, permitting play against different styles of opponent. Engines often have a simple text command-line interface, while GUIs may offer a variety of piece sets, board styles, or even 3D or animated pieces. Because recent engines are so capable, engines or GUIs may offer some way of handicapping the engine's ability, to improve the odds for a win by the human player. Universal Chess Interface (UCI) engines such as Fritz or Rybka may have a built-in mechanism for reducing the Elo rating of the engine (via UCI's uci_limitstrength and uci_elo parameters). Some versions of Fritz have a Handicap and Fun mode for limiting the current engine or changing the percentage of mistakes it makes or changing its style. Fritz also has a Friend Mode where during the game it tries to match the level of the player.

After discovering refutation screening—the application of alpha–beta pruning to optimizing move evaluation—in 1957, a team at Carnegie Mellon University predicted that a computer would defeat the world human champion by 1967.[19] It did not anticipate the difficulty of determining the right order to evaluate moves. Researchers worked to improve programs' ability to identify killer heuristics, unusually high-scoring moves to reexamine when evaluating other branches, but into the 1970s most top chess players believed that computers would not soon be able to play at a Master level.[20] In 1968, International Master David Levy made a famous bet that no chess computer would be able to beat him within ten years,[21] and in 1976 Senior Master and professor of psychology Eliot Hearst of Indiana University wrote that "the only way a current computer program could ever win a single game against a master player would be for the master, perhaps in a drunken stupor while playing 50 games simultaneously, to commit some once-in-a-year blunder".

The sudden improvement without a theoretical breakthrough was unexpected, as many did not expect that Belle's ability to examine 100,000 positions a second—about eight plies—would be sufficient. The Spracklens, creators of the successful microcomputer program Sargon, estimated that 90% of the improvement came from faster evaluation speed and only 10% from improved evaluations. New Scientist stated in 1982 that computers "play terrible chess ... clumsy, inefficient, diffuse, and just plain ugly", but humans lost to them by making "horrible blunders, astonishing lapses, incomprehensible oversights, gross miscalculations, and the like" much more often than they realized; "in short, computers win primarily through their ability to find and exploit miscalculations in human initiatives".

With increasing processing power and improved evaluation functions, chess programs running on commercially available workstations began to rival top-flight players. In 1998, Rebel 10 defeated Viswanathan Anand, who at the time was ranked second in the world, by a score of 5–3. However, most of those games were not played at normal time controls. Out of the eight games, four were blitz games (five minutes plus five seconds Fischer delay for each move); these Rebel won 3–1. Two were rapid games (fifteen minutes for each side) that Rebel won as well (1½–½). Finally, two games were played as regular tournament games with classic time controls (forty moves in two hours, one hour sudden death); here it was Anand who won ½–1½.[24] In fast games, computers played better than humans, but at classical time controls – at which a player's rating is determined – the advantage was not so clear.

n October 2002, Vladimir Kramnik and Deep Fritz competed in the eight-game Brains in Bahrain match, which ended in a draw. Kramnik won games 2 and 3 by "conventional" anti-computer tactics – play conservatively for a long-term advantage the computer is not able to see in its game tree search. Fritz, however, won game 5 after a severe blunder by Kramnik. Game 6 was described by the tournament commentators as "spectacular". Kramnik, in a better position in the early middlegame, tried a piece sacrifice to achieve a strong tactical attack, a strategy known to be highly risky against computers who are at their strongest defending against such attacks. True to form, Fritz found a watertight defense and Kramnik's attack petered out leaving him in a bad position. Kramnik resigned the game, believing the position lost. However, post-game human and computer analysis has shown that the Fritz program was unlikely to have been able to force a win and Kramnik effectively sacrificed a drawn position. The final two games were draws. Given the circumstances, most commentators still rate Kramnik the stronger player in the match.

The earliest attempts at procedural representations of playing chess predated the digital electronic age, but it was the stored program digital computer that gave scope to calculating such complexity. Claude Shannon, in 1949, laid out the principles of algorithmic solution of chess. In that paper, the game is represented by a "tree", or digital data structure of choices (branches) corresponding to moves. The nodes of the tree were positions on the board resulting from the choices of move. The impossibility of representing an entire game of chess by constructing a tree from first move to last was immediately apparent: there are an average of 36 moves per position in chess and an average game lasts about 35 moves to resignation (60-80 moves if played to checkmate, stalemate, or other draw). There are 400 positions possible after the first move by each player, about 200,000 after two moves each, and nearly 120 million after just 3 moves each.

The equivalent of this in computer chess are evaluation functions for leaf evaluation, which correspond to the human players' pattern recognition skills, and the use of machine learning techniques in training them, such as Texel tuning, stochastic gradient descent, and reinforcement learning, which corresponds to building experience in human players. This allows modern programs to examine some lines in much greater depth than others by using forwards pruning and other selective heuristics to simply not consider moves the program assume to be poor through their evaluation function, in the same way that human players do. The only fundamental difference between a computer program and a human in this sense is that a computer program can search much deeper than a human player could, allowing it to search more nodes and bypass the horizon effect to a much greater extent than is possible with human players.

Computer chess programs usually support a number of common de facto standards. Nearly all of today's programs can read and write game moves as Portable Game Notation (PGN), and can read and write individual positions as Forsyth–Edwards Notation (FEN). Older chess programs often only understood long algebraic notation, but today users expect chess programs to understand standard algebraic chess notation.

One particular type of search algorithm used in computer chess are minimax search algorithms, where at each ply the "best" move by the player is selected; one player is trying to maximize the score, the other to minimize it. By this alternating process, one particular terminal node whose evaluation represents the searched value of the position will be arrived at. Its value is backed up to the root, and that evaluation becomes the valuation of the position on the board. This search process is called minimax.

A naive implementation of the minimax algorithm can only search to a small depth in a practical amount of time, so various methods have been devised to greatly speed the search for good moves. Alpha–beta pruning, a system of defining upper and lower bounds on possible search results and searching until the bounds coincided, is typically used to reduce the search space of the program.

In addition, various selective search heuristics, such as quiescence search, forward pruning, search extensions and search reductions, are also used as well. These heuristics are triggered based on certain conditions in an attempt to weed out obviously bad moves (history moves) or to investigate interesting nodes (e.g. check extensions, passed pawns on seventh rank, etc.). These selective search heuristics have to be used very carefully however. If the program overextends, it wastes too much time looking at uninteresting positions. If too much is pruned or reduced, there is a risk of cutting out interesting nodes.

Of course, faster hardware and additional memory can improve chess program playing strength. Hyperthreaded architectures can improve performance modestly if the program is running on a single core or a small number of cores. Most modern programs are designed to take advantage of multiple cores to do parallel search. Other programs are designed to run on a general purpose computer and allocate move generation, parallel search, or evaluation to dedicated processors or specialized co-processors.

In the 1980s and 1990s, progress was finally made in the selective search paradigm, with the development of quiescence search, null move pruning, and other modern selective search heuristics. These heuristics had far fewer mistakes than earlier heuristics did, and was found to be worth the extra time it saved because it could search deeper and widely adopted by many engines. While many modern programs do use alpha-beta search as a substrate for their search algorithm, these additional selective search heuristics used in modern programs means that the program no longer does a "brute force" search. Instead they heavily rely on these selective search heuristics to extend lines the program considers good and prune and reduce lines the program considers bad, to the point where most of the nodes on the search tree are pruned away, enabling modern programs to search very deep.
"""


MARKOV_CHAIN = MarkovChain(TRAINING_DATA.replace("\n", "<br> ").split(), 1)
