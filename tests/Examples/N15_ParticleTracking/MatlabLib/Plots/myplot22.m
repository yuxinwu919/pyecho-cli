function myplot2(w1,w2)
%plot(w1(:,1),w1(:,2),w2(:,1),w2(:,2)*k)
k=max(abs(w1(:,2)))/max(abs(w2(:,2)));
plot(w1(:,1),w1(:,2),w2(:,1),w2(:,2)*k)