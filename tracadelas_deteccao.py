import numpy as np
from scipy import ndimage, misc, signal


def rotate( dimensao , angle):
    slope = np.tan(np.deg2rad(angle))
    b = dimensao / 2 * (1 - slope)
    R = np.zeros((dimensao, dimensao), float)

    for x in range(dimensao):
        R[int(slope * x + b)][x] = 1.
    return R

def repetiu_3x(array1, array2, array3):
    repetidos = []
    for i in range(len(array1)):

        if (array1[i] in array2 and array1[i] in array3) or (array1[i]+1 in array2 and array1[i]+1 in array3) or ((array1[i]-1 in array2 and array1[i]-1 in array3)):
            repetidos.append( array1[i] )
    return repetidos

def identifica_picos_seguidos(lista_de_picos):
    coord_repetidos = []
    for i in range( 0, len(lista_de_picos)-3 ):
        if lista_de_picos[i][-1] == lista_de_picos[i+1][-1]-1 and lista_de_picos[i][-1] == lista_de_picos[i+2][-1]-2:
            rep = repetiu_3x( lista_de_picos[i][0], lista_de_picos[i+1][0], lista_de_picos[i+2][0] )
            coord_repetidos.append( [np.array(rep), lista_de_picos[i][-1]] )
    return coord_repetidos


def image_analyzer(name, threshold=10, resize=0.7, d_blur=0.02, N_linhas_verticais=50, angle=0,grafico="nao"):  # name corresponde ao nome da imagem a analisar ... deve conter o '.jpg'

    im_inicial = misc.imresize(np.uint8(ndimage.imread(name, flatten=True)), resize)  # reading image

    altura, largura = np.shape(im_inicial)
    dim = int(largura * d_blur + 1)  # dimensao da matriz de convolucao

    M = rotate(dim, angle)

    im = signal.convolve2d(im_inicial, M, mode="valid")  # convolucao (passo mais demorado)

    picos = 0
    derivadas = []
    passo = int(np.shape(im)[1] / (N_linhas_verticais - 1))
    noises = []
    todos_picos = []

    for i in range(0, np.shape(im)[1], passo):  # percorrer todas as linhas verticais igualmente espacadas
        plot_profile = im[:, i]
        derivada = np.diff(plot_profile)**2  # derivada do perfil duma linha vertical
        derivadas.append(derivada)

        noise = np.mean(derivada) + np.std(derivada) * threshold
        noises.append(noise)

        #plt.figure(i)
        #plt.plot(derivada)
        #plt.plot(np.ones(len(derivada))*noise)

        lista_picos = np.where(derivada >= noise)[0]

        if len(lista_picos) > 0:
            picos += 1
            todos_picos.append([lista_picos, i / passo])

    if picos >= 0.8 * N_linhas_verticais:  # and suposto == "nao") or (picos < N_linhas_verticais and suposto == "sim"):    # Se passou do threshold em todas as linhas - sera defeito
        return True, 'lycra normal'


    if len(todos_picos) >= 3:
        picos_repetidos = identifica_picos_seguidos(todos_picos)

    else:
        picos_repetidos = []


    if len(picos_repetidos) >= 1:
        return True, 'tracadelas'
    else:
        return False


if __name__ == "__main__":
    print(image_analyzer("9.jpg", grafico="sim"))

