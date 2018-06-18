from scipy import ndimage, misc, signal
import numpy as np
import time


def rotate( dimensao , angle):
    slope = np.tan(np.deg2rad(angle))
    b = dimensao / 2 * (1 - slope)
    R = np.zeros((dimensao, dimensao), float)

    for x in range(dimensao):
        R[int(slope * x + b)][x] = 1.
        R[int(slope * x + b)+1][x] = 1.
        R[int(slope * x + b)-1][x] = 1.
        R[int(slope * x + b) + 2][x] = 1.
        R[int(slope * x + b) - 2][x] = 1.
    R = np.rot90(R)
    return R

def imagem_com_setas(imagem , lista_de_picos, passo):
    for i in lista_de_picos:
        for j in i[0]:
            imagem[ i[-1]*passo ][ j ] = 0

    return imagem

def repetiu_3x(array1, array2, array3):

    repetidos = []
    #print array1, array2, array3
    for i in range(len(array1)):

        if (array1[i] in array2 and array1[i] in array3) or (array1[i]+1 in array2 and array1[i]+1 in array3) or ((array1[i]-1 in array2 and array1[i]-1 in array3)):
            repetidos.append( array1[i] )
    #print repetidos
    return repetidos

def identifica_picos_seguidos(lista_de_picos):

    coord_repetidos = []

    for i in range( 0, len(lista_de_picos)-3 ):
        if lista_de_picos[i][-1] == lista_de_picos[i+1][-1]-1 and lista_de_picos[i][-1] == lista_de_picos[i+2][-1]-2:

            #print(lista_de_picos[i][-1], lista_de_picos[i + 1][-1], lista_de_picos[i + 2][-1])
            #print('repetidos existem')

            rep = repetiu_3x( lista_de_picos[i][0], lista_de_picos[i+1][0], lista_de_picos[i+2][0] )

            coord_repetidos.append( [np.array(rep), lista_de_picos[i][-1]] )

    return coord_repetidos


def funcao_detecao_agulhas(name, threshold = 9., resize = 0.5, d_blur = 0.04 , N_linhas_verticais = 70, angle = 0 , grafico = "nao"):   #name corresponde ao nome da imagem a analisar ... deve conter o '.jpg'

    im = misc.imresize( np.uint8( ndimage.imread( name , flatten=True) ) , resize)     #reading image

    altura, largura = np.shape(im)
    dim = int(largura * d_blur + 1)  # dimensao da matriz de convolucao

    M = rotate(dim, angle)

    im_blured = signal.fftconvolve(im, M, mode="valid")  # convolucao (passo mais demorado)

    picos = 0
    derivadas = []
    noises = []        # descomentar em caso de querer ver imagens
    passo = int(np.shape(im_blured)[0] / (N_linhas_verticais - 1))
    todos_picos = []

    for i in range(0, np.shape(im_blured)[0], passo ) :   #percorrer todas as linhas verticais igualmente espacadas
        plot_profile = im_blured[i]
        derivada  =  (np.diff(plot_profile))**2    # derivada do perfil duma linha vertical
        derivadas.append(derivada)
        noise = np.mean(derivada) + np.std(derivada)*threshold
        noises.append(noise)

        lista_picos = np.where(derivada >= noise)[0]

        if len(lista_picos) > 0:
            picos += 1
            todos_picos.append([lista_picos, i / passo])

    ######################################## comentar para imagem ###################################
    if grafico == "sim":

        import matplotlib.pyplot as plt  # descomentar em caso de querer ver imagens
        import os
        import copy

        if len(todos_picos) >= 3:
            im_com_setas = copy.deepcopy(im_blured)
            im_com_setas = imagem_com_setas(im_com_setas, todos_picos, passo)
            picos_repetidos = identifica_picos_seguidos(todos_picos)
            #print(picos_repetidos)
            im_repetidos = copy.deepcopy(im_blured)
            im_repetidos = imagem_com_setas(im_repetidos, picos_repetidos, passo)

        if not os.path.exists('deffect_profile_%s' % name):
            os.makedirs('deffect_profile_%s' % name)

        misc.imsave("deffect_profile_%s/blured.jpg" % name, im_blured)
        misc.imsave("deffect_profile_%s/repetidos.jpg" % name, im_repetidos)
        misc.imsave("deffect_profile_%s/rkernel.jpg" % name, M)

        if len(todos_picos) >= 3:
            misc.imsave("deffect_profile_%s/detecao.jpg" % name, im_com_setas)

        for i in range(len(derivadas)):
            fig = plt.figure('%s_%s' % (name,i))
            plt.plot(derivadas[i])
            plt.plot(np.ones(len(derivadas[i])) * noises[i], '-k')  # plot threshold line
            fig.savefig('deffect_profile_%s/subplots%s.jpg' % (name,i))

    ########################################    ########################################

    if picos >= 0.8*N_linhas_verticais: # and suposto == "nao") or (picos < N_linhas_verticais and suposto == "sim"):    # Se passou do threshold em todas as linhas - sera defeito
        return True
    else:
        return False


if __name__ == "__main__":
    start = time.time()
    print(funcao_detecao_agulhas("5.jpg",grafico="nao"))
    end = time.time()
    print(end-start)
